"""
Streamlit Secrets Helper Utility
Provides a centralized way to access secrets from Streamlit's secrets.toml file
"""

from typing import Any
from constants import *
import streamlit as st


class StreamlitSecretsHelper:
    """
    Helper class to access Streamlit secrets in a centralized and type-safe manner
    """

    @staticmethod
    def get_openai_api_key() -> str:
        """Get OpenAI API key from secrets"""
        return StreamlitSecretsHelper.get_secret(OPENAI_API_KEY)

    @staticmethod
    def get_jira_server_url() -> str:
        """Get JIRA server URL from secrets"""
        return StreamlitSecretsHelper.get_secret(JIRA_SERVER_URL)
    
    @staticmethod
    def get_jira_api_token() -> str:
        """Get JIRA API token from secrets"""
        return StreamlitSecretsHelper.get_secret(JIRA_API_TOKEN)

    @staticmethod
    def get_atsp_vs_id() -> str:
        """Get ATSP vector store ID from secrets"""
        return StreamlitSecretsHelper.get_secret(ATSP_VS_ID)
    
    @staticmethod
    def get_evt_atf_master_vs_id() -> str:
        """Get EVT ATF master vector store ID from secrets"""
        return StreamlitSecretsHelper.get_secret(EVT_ATF_MASTER_VS_ID)
    
    @staticmethod
    def get_evt_libzebra_master_vs_id() -> str:
        """Get EVT LibZebra master vector store ID from secrets"""
        return StreamlitSecretsHelper.get_secret(EVT_LIBZEBRA_MASTER_VS_ID)

    @staticmethod
    def get_secret(name: str) -> Any:
        """
        Get a secret value from Streamlit secrets
        
        Args:
            name: The name of the secret key
            
        Returns:
            The secret value
            
        Raises:
            KeyError: If the secret key is not found
        """
        try:
            return st.secrets[name]
        except KeyError:
            st.error(f"Secret '{name}' not found in secrets.toml")
            raise