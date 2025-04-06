######################
# Model Configuration
######################

# Model name to use for Cohere API calls (get the latest model from https://docs.cohere.com/docs/models)
MODEL_NAME = "command-a-03-2025"


######################
# Prompt Configuration
######################

# The initial system prompt that defines the AI's role and capabilities.
# You can customize this to change the AI's behavior or knowledge about the workspace.
SYSTEM_PROMPT_TEMPLATE = """You are a helpful AI assistant named Cohere, running in the terminal.
You have access to the user's current workspace: {workspace_context}
You can read files from this directory when answering questions using the read_file tool.
Always provide context-aware responses considering the current workspace. Be concise but informative."""


######################
# UI/Display Configuration
######################

# The name displayed for the user in the chat interface.
USER_LABEL = "You"

# The name displayed for the AI assistant in the chat interface.
ASSISTANT_LABEL = "Cohere"

# Timestamp format
TIMESTAMP_FORMAT = "%H:%M:%S"

# Maximum depth to scan for files in the workspace context
MAX_SCAN_DEPTH = 5

# Maximum number of files to list in the workspace context
MAX_FILES_CONTEXT = 50

VERSION = "0.1.0"
