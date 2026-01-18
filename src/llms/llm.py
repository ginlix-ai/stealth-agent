import os
import json
from pathlib import Path
from typing import Dict, Optional, Any
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from langchain_core.language_models import BaseChatModel
from langchain_deepseek import ChatDeepSeek
from langchain_qwq import ChatQwen

load_dotenv()


class ModelConfig:
    """Manages model configuration from JSON files."""
    
    def __init__(self):
        # Load llm_config for model parameters
        llm_config_path = Path(__file__).parent / "llm_config.json"
        with open(llm_config_path, 'r') as f:
            self.llm_config = json.load(f)
        
        # Load llm_manifest for token tracking and provider info
        manifest_path = Path(__file__).parent / "llm_manifest.json"
        with open(manifest_path, 'r') as f:
            self.manifest = json.load(f)
    
    def get_model_config(self, model_id: str) -> Optional[Dict]:
        """Get model configuration from llm_config."""
        return self.llm_config.get(model_id)
    
    def get_provider_info(self, provider: str) -> Dict:
        """Get provider configuration from manifest."""
        return self.manifest["provider_config"].get(provider, {})
    
    def get_model_pricing(self, custom_model_name: str) -> Optional[Dict[str, Any]]:
        """Get pricing information for a specific model from manifest."""
        # Get model info from llm_config first
        model_info = self.llm_config.get(custom_model_name)
        if not model_info:
            return None

        provider = model_info["provider"]
        model_id = model_info["model_id"]

        # Then look up pricing in manifest
        models = self.manifest["models"].get(provider, [])
        for model in models:
            if model["id"] == model_id:
                return model.get('pricing')
        return None

    def get_model_info(self, provider: str, model_id: str) -> Optional[Dict[str, Any]]:
        """Get full model information from manifest by provider and model_id.

        Args:
            provider: Provider name (e.g., 'openai', 'anthropic', 'volcengine')
            model_id: Model ID (e.g., 'gpt-5', 'claude-opus-4', 'doubao-seed-1-6-250615')

        Returns:
            Model info dictionary with pricing, parameters, etc., or None if not found
        """
        models = self.manifest["models"].get(provider, [])
        for model in models:
            if model["id"] == model_id:
                return model
        return None


class LLM:
    """Factory class for creating LangChain LLM clients."""
    
    # Class-level model config instance
    _model_config = None
    
    @classmethod
    def get_model_config(cls) -> ModelConfig:
        """Get or create the model configuration singleton."""
        if cls._model_config is None:
            cls._model_config = ModelConfig()
        return cls._model_config
    
    def __init__(self, model: str, **override_params):
        """
        Initializes the LLM factory.

        Args:
            model: The customized model name (key in llm_config.json).
            **override_params: Additional parameters to override defaults.
        """
        self.model_config = self.get_model_config()
        
        # Get model configuration from llm_config.json
        model_info = self.model_config.get_model_config(model)
        if not model_info:
            raise ValueError(f"Model {model} not found in llm_config.json")
        
        self.custom_model_name = model  # Store the custom name
        self.model = model_info["model_id"]  # Use model_id for API calls
        self.provider = model_info["provider"]
        self.parameters = model_info.get("parameters", {}).copy()
        
        # Override with any provided parameters
        self.parameters.update(override_params)

        # Get provider info from manifest
        self.provider_info = self.model_config.get_provider_info(self.provider)

        # Extract provider configuration
        self.sdk = self.provider_info.get("sdk")
        self.env_key = self.provider_info.get("env_key")
        self.base_url = self.provider_info.get("base_url")

        # Store response API flag for OpenAI SDK
        self.use_response_api = self.provider_info.get("use_response_api", False) if self.sdk == "openai" else False

    def get_llm(self):
        """
        Initializes and returns a LangChain LLM client for the configured provider.

        Returns:
            A LangChain chat model instance.

        Raises:
            ValueError: If required API keys are not set or provider is unsupported.
        """
        # Use the resolved SDK (already determined in __init__)
        if self.sdk == "openai":
            return self._get_openai_llm()
        elif self.sdk == "deepseek":
            return self._get_deepseek_llm()
        elif self.sdk == "qwq":
            return self._get_qwq_llm()
        elif self.sdk == "anthropic":
            return self._get_anthropic_llm()
        elif self.sdk == "gemini":
            return self._get_gemini_llm()
        else:
            raise ValueError(f"Unsupported SDK: {self.sdk} for provider {self.provider}")
    
    def _get_openai_llm(self):
        """Get OpenAI or OpenAI-compatible LLM."""
        params = {
            "model": self.model,
            "stream_usage": True,
            "max_retries": 5,
            "timeout": 600.0,  # 10 minutes - sufficient for long reasoning
        }

        # Set API key from provider configuration
        if self.env_key:
            params["api_key"] = os.getenv(self.env_key)
            if not params["api_key"]:
                raise ValueError(f"{self.env_key} environment variable is not set")
        else:
            # Special case for local providers without API key
            params["api_key"] = "lm-studio" if self.provider == "lm-studio" else "EMPTY"

        # Set base URL from provider configuration
        if self.base_url:
            # Handle HOST_IP replacement for local providers
            if "{HOST_IP}" in self.base_url:
                host_ip = os.getenv("HOST_IP")
                if not host_ip:
                    raise ValueError(f"HOST_IP environment variable is not set for {self.provider}")
                params["base_url"] = self.base_url.replace("{HOST_IP}", host_ip)
            else:
                params["base_url"] = self.base_url
        
        # Handle Response API if configured
        if self.use_response_api:
            params["output_version"] = "responses/v1"

        # Auto-enable use_previous_response_id for responses API models
        if self.use_response_api or "reasoning" in self.parameters:
            params["use_previous_response_id"] = True

        # Add all parameters from llm_config
        params.update(self.parameters)
        
        return ChatOpenAI(**params)

    def _get_deepseek_llm(self):
        """Get DeepSeek or DeepSeek-compatible LLM."""
        params = {
            "model": self.model,
            "stream_usage": True,
            "max_retries": 5,
            "timeout": 600.0,  # 10 minutes - sufficient for long reasoning
        }

        # Set API key from provider configuration
        if self.env_key:
            params["api_key"] = os.getenv(self.env_key)
            if not params["api_key"]:
                raise ValueError(f"{self.env_key} environment variable is not set")
        else:
            # Special case for local providers without API key
            params["api_key"] = "EMPTY"

        # Set base URL from provider configuration (ChatDeepSeek uses api_base)
        if self.base_url:
            # Handle HOST_IP replacement for local providers
            if "{HOST_IP}" in self.base_url:
                host_ip = os.getenv("HOST_IP")
                if not host_ip:
                    raise ValueError(f"HOST_IP environment variable is not set for {self.provider}")
                params["api_base"] = self.base_url.replace("{HOST_IP}", host_ip)
            else:
                params["api_base"] = self.base_url


        # Add all parameters from llm_config
        params.update(self.parameters)

        return ChatDeepSeek(**params)

    def _get_qwq_llm(self):
        """Get QwQ or QwQ-compatible LLM (for Qwen models with reasoning support)."""
        params = {
            "model": self.model,
            "stream_usage": True,
            "max_retries": 5,
            "timeout": 600.0,  # 10 minutes - sufficient for long reasoning
        }

        # Set API key from provider configuration
        if self.env_key:
            params["api_key"] = os.getenv(self.env_key)
            if not params["api_key"]:
                raise ValueError(f"{self.env_key} environment variable is not set")
        else:
            # Special case for local providers without API key
            params["api_key"] = "EMPTY"

        # Set base URL from provider configuration (ChatQwQ uses api_base)
        if self.base_url:
            # Handle HOST_IP replacement for local providers
            if "{HOST_IP}" in self.base_url:
                host_ip = os.getenv("HOST_IP")
                if not host_ip:
                    raise ValueError(f"HOST_IP environment variable is not set for {self.provider}")
                params["api_base"] = self.base_url.replace("{HOST_IP}", host_ip)
            else:
                params["api_base"] = self.base_url


        # Add all parameters from llm_config
        params.update(self.parameters)

        return ChatQwen(**params)

    def _get_anthropic_llm(self):
        """Get Anthropic LLM."""
        from langchain_anthropic import ChatAnthropic

        params = {
            "model": self.model,
            "api_key": os.getenv(self.env_key) if self.env_key else None,
            "max_retries": 5,
            "timeout": 600.0,  # 10 minutes - sufficient for long reasoning
        }

        if not params["api_key"]:
            raise ValueError(f"{self.env_key or 'ANTHROPIC_API_KEY'} environment variable is not set")

        # Set base URL from provider configuration if available
        if self.base_url:
            params["base_url"] = self.base_url


        # Add all parameters from llm_config, excluding enable_caching
        # (enable_caching is not a ChatAnthropic parameter, it's used by our caching logic)
        filtered_params = {k: v for k, v in self.parameters.items() if k != "enable_caching"}
        params.update(filtered_params)

        return ChatAnthropic(**params)
    
    def _get_gemini_llm(self):
        """Get Gemini LLM."""
        from langchain_google_genai import ChatGoogleGenerativeAI
        params = {
            "model": self.model,
            "api_key": os.getenv(self.env_key) if self.env_key else None,
            "timeout": 600.0,  # 10 minutes - sufficient for long reasoning
        }

        if not params["api_key"]:
            raise ValueError(f"{self.env_key or 'GEMINI_API_KEY'} environment variable is not set")
        

        # Add all parameters from llm_config
        params.update(self.parameters)
        
        return ChatGoogleGenerativeAI(**params)


# Backward compatibility functions
def create_llm(model: str, **kwargs):
    """
    Convenience function for creating an LLM instance.
    
    Args:
        model: The model name
        **kwargs: Additional parameters to override
    
    Returns:
        A LangChain chat model instance
    """
    return LLM(model, **kwargs).get_llm()


def get_llm_by_type(llm_type: str) -> BaseChatModel:
    """
    Get LLM instance by type.
    Supports both legacy type names and direct model names.

    Args:
        llm_type: The LLM type or model name (e.g., 'basic', 'reasoning', 'gpt-4o')

    Returns:
        A LangChain chat model instance
    """
    try:
        llm = LLM(llm_type).get_llm()
        return llm
    except ValueError as e:
        raise ValueError(f"Unknown LLM type or model: {llm_type}. Error: {e}")


def get_configured_llm_models() -> dict[str, list[str]]:
    """
    Get all configured LLM models grouped by provider.

    Returns:
        Dictionary mapping provider to list of configured model names.
    """
    try:
        config = ModelConfig()
        models: dict[str, list[str]] = {}

        # Group all models by provider
        for model_name in config.llm_config.keys():
            model_info = config.get_model_config(model_name)
            if model_info:
                provider = model_info.get("provider", "unknown")
                models.setdefault(provider, []).append(model_name)

        return models

    except Exception as e:
        # Log error and return empty dict to avoid breaking the application
        print(f"Warning: Failed to load LLM configuration: {e}")
        return {}
    
def should_enable_caching(model_name: str) -> bool:
    """
    Check if a model should enable Anthropic prompt caching.

    Args:
        model_name: The model name from llm_config.json

    Returns:
        True if the model has enable_caching=True in its parameters
    """
    try:
        config = ModelConfig()
        model_info = config.get_model_config(model_name)
        if not model_info:
            return False

        # Check if model has enable_caching in parameters
        parameters = model_info.get("parameters", {})
        return parameters.get("enable_caching", False)
    except Exception:
        return False


## Important Note:
# 1. The llm_config.json file is used to store the detailed model configuration and name mapping.
# 2. The llm_manifest.json file is used:
#    - to store the model pricing information and model parameters
#    - to store the model parameters from the model providers.
#    - to store the providers information including the SDK, base URL, environment key.
# We assume all the configurations in the llm_config.json file are valid and complete - always validate the configurations when adding new models.