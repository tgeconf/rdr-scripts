#!/usr/bin/env python3
"""
Environment loader for .env file support
"""

import os
from typing import Dict, Optional


def load_env_file(env_file: str = ".env") -> Dict[str, str]:
    """
    Load environment variables from a .env file

    Args:
        env_file: Path to the .env file (default: '.env')

    Returns:
        Dictionary of environment variables
    """
    env_vars = {}

    if not os.path.exists(env_file):
        print(f"Warning: {env_file} file not found")
        return env_vars

    try:
        with open(env_file, "r", encoding="utf-8") as f:
            for line_num, line in enumerate(f, 1):
                line = line.strip()

                # Skip empty lines and comments
                if not line or line.startswith("#"):
                    continue

                # Parse key=value pairs
                if "=" in line:
                    key, value = line.split("=", 1)
                    key = key.strip()
                    value = value.strip()

                    # Remove quotes if present
                    if value.startswith('"') and value.endswith('"'):
                        value = value[1:-1]
                    elif value.startswith("'") and value.endswith("'"):
                        value = value[1:-1]

                    env_vars[key] = value
                    os.environ[key] = value
                else:
                    print(f"Warning: Invalid line {line_num} in {env_file}: {line}")

    except Exception as e:
        print(f"Error reading {env_file}: {e}")

    return env_vars


def check_required_env_vars() -> bool:
    """
    Check if all required environment variables are set

    Returns:
        True if all required variables are set, False otherwise
    """
    # Check for embedding API key
    embedding_api_key = os.environ.get("VOLC_LLM_KEY") or os.environ.get("ARK_API_KEY")
    base_url = os.environ.get("EMBEDDING_BASE_URL")
    model = os.environ.get("EMBEDDING_MODEL")

    # Check for chat model API key
    chat_api_key = os.environ.get("DS_API_KEY")

    missing_vars = []

    if not embedding_api_key:
        missing_vars.append("VOLC_LLM_KEY (or ARK_API_KEY) - for embedding model")
    if not base_url:
        missing_vars.append("EMBEDDING_BASE_URL - for embedding model")
    if not model:
        missing_vars.append("EMBEDDING_MODEL - for embedding model")
    if not chat_api_key:
        missing_vars.append("DS_API_KEY - for chat model")

    if missing_vars:
        print(f"Missing required environment variables: {missing_vars}")
        print("Please set them in your .env file or system environment")
        return False

    print("✓ All required environment variables are set")
    print(
        f"  Embedding API Key: {'VOLC_LLM_KEY' if os.environ.get('VOLC_LLM_KEY') else 'ARK_API_KEY'}"
    )
    print(f"  Chat API Key: DS_API_KEY")
    print(f"  Base URL: {base_url}")
    print(f"  Model: {model}")
    return True


def create_env_template(env_file: str = ".env") -> None:
    """
    Create a template .env file with example values

    Args:
        env_file: Path to create the .env file (default: '.env')
    """
    template = """# Environment configuration for data synthesis pipeline
# Fill in your actual values below

# Chat Model API Configuration (for text generation)
DS_API_KEY=your-deepseek-chat-api-key-here

# Embedding Model API Configuration (for embeddings)
VOLC_LLM_KEY=your-embedding-api-key-here
EMBEDDING_BASE_URL=https://ark.cn-beijing.volces.com/api/v3
EMBEDDING_MODEL=ep-20250903121149-5cdzn

# Alternative embedding API key names (for compatibility)
# ARK_API_KEY=your-embedding-api-key-here

# Example for DeepSeek embedding:
# VOLC_LLM_KEY=sk-your-deepseek-embedding-key
# EMBEDDING_BASE_URL=https://api.deepseek.com/v1
# EMBEDDING_MODEL=deepseek-embedding
"""

    if os.path.exists(env_file):
        response = input(f"{env_file} already exists. Overwrite? (y/N): ")
        if response.lower() != "y":
            print("Cancelled")
            return

    try:
        with open(env_file, "w", encoding="utf-8") as f:
            f.write(template)
        print(f"Created {env_file} template file")
        print(f"Please edit {env_file} with your actual API credentials")
    except Exception as e:
        print(f"Error creating {env_file}: {e}")


if __name__ == "__main__":
    print("=== Environment Configuration Tool ===")
    print("1. Create .env template")
    print("2. Load and check .env file")

    choice = input("\nChoose an option (1/2): ").strip()

    if choice == "1":
        create_env_template()
    elif choice == "2":
        print("\nLoading .env file...")
        env_vars = load_env_file()
        print(f"Loaded {len(env_vars)} variables from .env")
        check_required_env_vars()
    else:
        print("Invalid choice")
