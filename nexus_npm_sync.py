import os
import json
import httpx
import anyio
import itertools
import signal
from pathlib import Path
import aiofiles
import fnmatch
import argparse
import libs.log as log
import libs.config as config

APP_NAME = "Nexus NPM Syncer"

class NexusSyncer:

  CONFIG = {}
  HEADERS = {"Accept": "application/json"}
  CONFIG_FILE = "config.yaml"

  async def download_file(self, url, dest_path):
    try:
      if Path(dest_path).exists():
          self.logger.warning(f"File {dest_path} already downloaded, skipping...")
          return True
      self.logger.info(f"Downloading {dest_path} from {url}...")
      async with httpx.AsyncClient(timeout=60) as client:
        async with client.stream("GET", url, headers=self.HEADERS, auth=self.SOURCE_NEXUS_AUTH) as response:
          response.raise_for_status()
          async with aiofiles.open(dest_path, "wb") as file:
            async for chunk in response.aiter_bytes():
              await file.write(chunk)
      self.logger.info(f"Download complete: {dest_path}")
      return True
    except (httpx.HTTPError, anyio.get_cancelled_exc_class()) as exc:
      self.logger.error(f"Error downloading {url}: {exc}")
      if os.path.exists(dest_path):
        try:
          os.remove(dest_path)
          self.logger.warning(f"Partial file {dest_path} removed due to interruption")
        except OSError as e:
          self.logger.error(f"Failed to remove {dest_path}: {e}")
    return False

  async def download_worker(self, sem, tasks_count, done_event, lock, url, path):
    async with sem:
      await self.download_file(url, path)
    async with lock:
      tasks_count[0] -= 1
      if tasks_count[0] == 0:
          done_event.set()

  async def upload_file(self, filepath):
    if not os.path.exists(filepath):
      self.logger.error(f"Can not upload file {filepath} - not found")
      return False
    files = {
      "npm.asset": (filepath, open(filepath, "rb"), "application/x-compressed")
    }
    try:
      self.logger.info(f"Uploading {filepath} ...")
      async with httpx.AsyncClient(timeout=60) as client:
        with open(filepath, "rb") as file:
          files = {"npm.asset": (filepath, file, "application/x-compressed")}
          response = await client.post(
              self.TARGET_REPO,
              auth=self.DEST_NEXUS_AUTH,
              files=files
          )
          if response.status_code in [200, 201, 204]:
            self.logger.info(f"Upload of {filepath} complete")
          elif response.status_code == 400:
            self.logger.warning(f"Package {filepath} already exists in destination repository")
          else:
            self.logger.error(f"Error uploading {filepath}: {response.status_code} {response.text}")
            return False
      return True
    except (httpx.HTTPError, anyio.get_cancelled_exc_class()) as exc:
      self.logger.error(f"Error uploading {filepath}: {exc}")
      return False

  async def upload_worker(self, sem, tasks_count, done_event, lock, path):
    async with sem:
      await self.upload_file(path)
    async with lock:
      tasks_count[0] -= 1
      if tasks_count[0] == 0:
          done_event.set()

  async def fetch_manifest(self, package):
    manifest_file = f"{self.DOWNLOAD_DIR}/{package.replace('@', '_at_').replace('/', '_')}.json"
    if Path(manifest_file).exists():
      self.logger.info(f"Using cached manifest: {manifest_file}")
      with open(manifest_file, "r") as file:
        return json.load(file)
    package_url = f"{self.SOURCE_REPO}/{package}".replace("@", "%40")
    self.logger.info(f"Fetching package manifest from {package_url} for package {package}")
    try:
      response = httpx.get(package_url, headers=self.HEADERS, auth=self.SOURCE_NEXUS_AUTH)
      response.raise_for_status()
      manifest = response.json()
      with open(manifest_file, "w") as file:
        json.dump(manifest, file)
      return manifest
    except Exception as e:
      self.logger.error(f"Error fetching manifest for {package}: {e}")
      return None

  async def find_tgz_files(self, directory):
    tgz_files = []
    for root, _, files in os.walk(directory):
      for file in fnmatch.filter(files, "*.tgz"):
        tgz_files.append(os.path.join(root, file))
    return tgz_files

  async def signal_handler(self, cancel_scope):
    with anyio.open_signal_receiver(signal.SIGINT, signal.SIGTERM) as signals:
      async for signum in signals:
        print(f"Received signal {signum}, cancelling tasks...")
        cancel_scope.cancel()
        break

  async def load_config(self):
    # Setup logger
    logger = log.setup_logger("load-config", logToFile=False, debug=False)
    logger.info(f"==== {APP_NAME} ====")
    logger.info(f"Loading config from {self.CONFIG_FILE}")
    cnf = config.load_config(self.CONFIG_FILE)
    if not cnf:
      logger.error("Failed to load config, exiting")
      return False
    self.SOURCE_REPO = f"{cnf["source"]["baseUrl"]}/repository/{cnf["source"]["repoName"]}"
    self.TARGET_REPO = f"{cnf["destination"]["baseUrl"]}/service/rest/v1/components?repository={cnf["destination"]["repoName"]}"
    if "username" in cnf["source"] and "password" in cnf["source"]:
      self.SOURCE_NEXUS_AUTH = httpx.BasicAuth(cnf["source"]["username"], cnf["source"]["password"])
    else:
      self.SOURCE_NEXUS_AUTH = None
    if "username" in cnf["destination"] and "password" in cnf["destination"]:
      self.DEST_NEXUS_AUTH = httpx.BasicAuth(cnf["destination"]["username"], cnf["destination"]["password"])
    else:
      self.DEST_NEXUS_AUTH = None
    self.DOWNLOAD_DIR = cnf["downloadPath"]
    self.MAX_CONCURRENT_DOWNLOADS = cnf["maxConcurrentDownloads"]
    self.MAX_CONCURRENT_UPLOADS = cnf["maxConcurrentUploads"]
    self.PACKAGES = cnf["packages"]
    self.REMOVE_LOACAL_PACKAGES = cnf["deleteLocalPackages"]
    self.LOG_TO_FILE = cnf["logging"]["logToFile"]
    self.DEBUG = cnf["logging"]["debug"]
    logger.info("Config loaded successfully")
    self.logger = log.setup_logger("nexus_npm_sync", logToFile=self.LOG_TO_FILE, debug=self.DEBUG)
    return True

  async def app(self, onlyDownload=False, onlyUpload=False, config_file="config.yaml"):
    # Load config
    self.CONFIG_FILE = config_file
    if not await self.load_config(): return

    # Prepare download directory
    os.makedirs(self.DOWNLOAD_DIR, exist_ok=True)
    
    # Fetch manifests
    for package in self.PACKAGES:
      tgz_files = []
      self.logger.info(f"Processing package {package}...")
      
      manifest = await self.fetch_manifest(package)
      if not manifest:
        continue
      package_name = package.replace('@', '_at_').replace('/', '_')
      os.makedirs(os.path.join(self.DOWNLOAD_DIR, package_name), exist_ok=True)
      for version, details in manifest["versions"].items():
        tgz_url = details["dist"]["tarball"]
        filename = os.path.basename(tgz_url)
        tgz_path = os.path.join(self.DOWNLOAD_DIR, package_name, filename)
        tgz_files.append((tgz_url, tgz_path))

      self.logger.info(f"Total versions is {len(tgz_files)} for package {package}")
      
      if not onlyUpload:
        # Download files
        done_event = anyio.Event()
        lock = anyio.Lock()
        sem_download = anyio.Semaphore(self.MAX_CONCURRENT_DOWNLOADS)
        tasks = [len(tgz_files)]
        with anyio.CancelScope() as cancel_scope:
          async with anyio.create_task_group() as tg:
            tg.start_soon(self.signal_handler, cancel_scope)
            for batch in itertools.zip_longest(*[iter(tgz_files)] * self.MAX_CONCURRENT_DOWNLOADS):
              for entry in batch:
                if entry is not None:
                  tg.start_soon(self.download_worker, sem_download, tasks, done_event, lock, *entry)
            await done_event.wait()
            cancel_scope.cancel()
        self.logger.info(f"All downloads complete for package {package}")

      # Upload files
      if not onlyDownload:
        done_event = anyio.Event()
        lock = anyio.Lock()
        tasks = [len(tgz_files)]
        sem_upload = anyio.Semaphore(self.MAX_CONCURRENT_UPLOADS)
        with anyio.CancelScope() as cancel_scope:
          async with anyio.create_task_group() as tg:
            tg.start_soon(self.signal_handler, cancel_scope)
            for batch in itertools.zip_longest(*[iter(tgz_files)] * self.MAX_CONCURRENT_UPLOADS):
              for entry in batch:
                if entry is not None:
                  tg.start_soon(self.upload_worker, sem_upload, tasks, done_event, lock, entry[1])
            await done_event.wait()
            cancel_scope.cancel()
        self.logger.info(f"All uploads complete for package {package}")

      # Cleanup
      if self.REMOVE_LOACAL_PACKAGES:
        self.logger.info(f"Removing local files of package {package}")
        for entry in tgz_files:
          if Path(entry[1]).exists():
            os.remove(entry[1])
        self.logger.info("Local packages removed")

if __name__ == "__main__":
  parser = argparse.ArgumentParser(
    description=APP_NAME,
    formatter_class=argparse.RawTextHelpFormatter,
    epilog='==============================='
  )
  parser.add_argument('-d', '--download', help="Only download packages from source repository", action='store_true')
  parser.add_argument('-u', '--upload', help="Only upload packages to target repository", action='store_true')
  parser.add_argument('-c', '--config', help="Path to config file (Default: config.yaml)", default="config.yaml")
  args = parser.parse_args()
  syncer = NexusSyncer()
  anyio.run(syncer.app, args.download, args.upload, args.config)
