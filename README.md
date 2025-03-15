# NPM Repository Synchronizer for Nexus
  
This tool will be useful if you need to migrate an NPM repository from your Nexus to another Nexus. Alternatively, if you need to transfer NPM packages from one repository in your Nexus to another repository (e.g., when changing the blob storage).
  
## Preparation
```shell
python3 -m venv .
source ./bin/activate
pip install -r ./requirements.txt
```

## Configuration
An example configuration file can be found in **config.yaml.example**

```yaml
# Section for the source Nexus
source:
  # Base URL
  baseUrl: https://nexus.domain.com
  # Repository name
  repoName: npm-repo
  # Authentication. If the repository is public, this can be omitted.
  username: user
  password: password

# Similar settings for the destination Nexus
destination:
  baseUrl: https://nexus-another.domain.com
  repoName: npm-repo
  username: user
  password: password

# Should downloaded packages be deleted after uploading them to the destination Nexus? (Default: false)
deleteLocalPackages: false
# Path to the directory where the synchronizer will store downloaded files (Default: npm-packages)
downloadPath: npm-packages
# Maximum number of concurrent downloads (Default: 30)
maxConcurrentDownloads: 30
# Maximum number of concurrent uploads (Default: 20)
maxConcurrentUploads: 20

# Logging settings
logging:
  debug: false
  # Should logs be written to a file (logs will be saved in logs/)
  logToFile: false

# List of packages
packages:
  - "@web/design"
  - "analytics"
```

### Minimal configuration example
```yaml
source:
  baseUrl: https://nexus.domain.com
  repoName: npm-repo

destination:
  baseUrl: https://nexus-another.domain.com
  repoName: npm-repo
  username: user
  password: password

packages:
  - "@web/design"
  - "analytics"
```

## Running
The synchronizer has the following options:
```shell
$ python ./nexus_npm_sync.py -h
usage: Nexus Syncer [-h] [-d] [-u] [-c CONFIG]

Nexus NPM repo syncer

options:
  -h, --help            show this help message and exit
  -d, --download        Only download packages from source repository
  -u, --upload          Only upload packages to target repository
  -c CONFIG, --config CONFIG
                        Path to config file (Default: config.yaml)

===============================
```
**-d, --download** - if you only need to download packages  
**-u, --upload** - if you only need to upload packages  
**-c file, --config file** - path to the config file (Default: config.yaml)

## Compiling to a Binary
```shell
apt-get install -y build-essential patchelf
pip install staticx pyinstaller
pyinstaller --onefile --clean --strip --log-level=DEBUG --hidden-import=libs.config --hidden-import=libs.log nexus_npm_sync.py
staticx ./dist/nexus_npm_sync ./nexus_npm_sync
```
After this, the statically built binary will be located in `./nexus_npm_sync`.  
This file can be placed in a scratch container and executed.
