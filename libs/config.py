import yaml
from . import log
from jsonschema import validate

schema = """
type: object
properties:
  source:
    type: object
    properties:
      baseUrl:
        type: string
      repoName:
        type: string
      username:
        type: string
      password:
        type: string
    required:
      - baseUrl
      - repoName
  destination:
    type: object
    properties:
      baseUrl:
        type: string
      repoName:
        type: string
      username:
        type: string
      password:
        type: string
    required:
      - baseUrl
      - repoName
  deleteLocalPackages:
    type: boolean
    default: false
  downloadPath:
    type: string
    default: npm-packages
  maxConcurrentDownloads:
    type: integer
    default: 30
  maxConcurrentUploads:
    type: integer
    default: 20
  logging:
    type: object
    properties:
      logToFile:
        type: boolean
        default: true
      debug:
        type: boolean
        default: false
  packages:
    type: array
    items:
      type: string
    required:
      - packages
"""

def load_config(config_path):
  logger = log.setup_logger("config", logToFile=False)
  try:
    with open(config_path, 'r') as file:
      config = yaml.safe_load(file)
      validate(instance=config, schema=yaml.safe_load(schema))
      return config
  except Exception as e:
    logger.error(f'Error loading config: {e}')
    return False
