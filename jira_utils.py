"""
JIRA utility functions for log analysis application
Handles JIRA authentication, project/bug fetching, and attachments
"""

import io
import streamlit as st
from jira import JIRA


# JIRA Configuration
# JIRA_SERVER = st.secrets["jira_server"]
# JIRA_API_TOKEN = st.secrets["jira_api_token"]


JIRA_SERVER =  "placeholder for JIRA_SERVER"
JIRA_API_TOKEN = "placeholder for JIRA_API_TOKEN"


@st.cache_resource
def get_jira_client():

    """Initialize and return JIRA client"""
    try:
        jira = JIRA(options={'server': JIRA_SERVER}, token_auth=JIRA_API_TOKEN)
        return jira
    except Exception as e:
        st.error(f"Failed to connect to JIRA: {str(e)}")
        return None


@st.cache_data
def get_jira_projects():
    """Fetch all JIRA projects"""
    jira = get_jira_client()
    if jira is None:
        return []
    
    try:
        projects = jira.projects()
        return [{"key": project.key, "name": project.name} for project in projects]
    except Exception as e:
        st.error(f"Error fetching JIRA projects: {str(e)}")
        return []


@st.cache_data(show_spinner=False)
def get_bugs_from_project(project_key):
    """Fetch all bugs from a JIRA project"""
    jira = get_jira_client()
    if jira is None:
        return []
    
    try:
        jql_query = f'project = {project_key} AND issuetype = Bug ORDER BY created DESC'
        bugs = jira.search_issues(jql_query, maxResults=False)  # No limit - fetch all bugs
        return [{"key": bug.key, "summary": bug.fields.summary} for bug in bugs]
    except Exception as e:
        st.error(f"Error fetching bugs from project {project_key}: {str(e)}")
        return []


@st.cache_data(show_spinner=False)
def get_bug_description(bug_key):
    """Fetch description of a specific bug"""
    jira = get_jira_client()
    if jira is None:
        return None
    
    try:
        issue = jira.issue(bug_key)
        return {
            "key": issue.key,
            "summary": issue.fields.summary,
            "description": issue.fields.description or "No description provided",
            "status": issue.fields.status.name,
            "priority": issue.fields.priority.name if issue.fields.priority else "No priority set",
            "assignee": issue.fields.assignee.displayName if issue.fields.assignee else "Unassigned"
        }
    except Exception as e:
        st.error(f"Error fetching bug details for {bug_key}: {str(e)}")
        return None


@st.cache_data(show_spinner=False)
def get_bug_attachments(bug_key):
    """Fetch attachments from a JIRA bug"""
    jira = get_jira_client()
    if jira is None:
        return []
    
    try:
        issue = jira.issue(bug_key)
        attachments = []
        
        if hasattr(issue.fields, 'attachment') and issue.fields.attachment:
            for attachment in issue.fields.attachment:
                # Filter for log files
                if any(ext in attachment.filename.lower() for ext in ['.log', '.txt', '.csv']):
                    attachments.append({
                        "id": attachment.id,
                        "filename": attachment.filename,
                        "size": attachment.size,
                        "created": attachment.created,
                        "author": attachment.author.displayName
                    })
        
        return attachments
    except Exception as e:
        st.error(f"Error fetching attachments for {bug_key}: {str(e)}")
        return []


def download_attachment(attachment_id, filename):
    """Download an attachment from JIRA and return as BytesIO object"""
    jira = get_jira_client()
    if jira is None:
        return None
    
    try:
        # Get the attachment object first
        attachment = jira.attachment(attachment_id)
        
        # Download the content using requests through the JIRA session
        response = jira._session.get(attachment.content, stream=True)
        response.raise_for_status()
        
        # Get the content as bytes
        attachment_bytes = response.content
        
        # Create a BytesIO object that mimics an uploaded file
        file_content = io.BytesIO(attachment_bytes)
        file_content.name = filename
        file_content.seek(0)  # Ensure we're at the beginning
        
        # Add attributes to make it compatible with Streamlit's uploaded file
        file_content.type = 'text/plain'  # Default type for log files
        file_content.size = len(attachment_bytes)
        
        # Add getvalue method compatibility
        def getvalue():
            current_pos = file_content.tell()
            file_content.seek(0)
            content = file_content.read()
            file_content.seek(current_pos)
            return content
        
        file_content.getvalue = getvalue
        
        return file_content
    except Exception as e:
        st.error(f"Error downloading attachment {filename}: {str(e)}")
        return None


def get_vector_store_mapping():
    """Get the mapping of JIRA projects to vector store IDs"""
    return {
        "ATSP": ["vs_placeholder_for_ATSP"],  # Zebra Print
        "ZSB": ["vs_placeholder_for_ZSB"],
        "EVT": ["vs_placeholder_for_EVT_1","vs_placeholder_for_EVT_2"]  # To be updated
        # Add more projects here as needed
    }


def is_project_supported(project_key):
    """Check if a project is supported (has vector store mapping)"""
    vector_store_mapping = get_vector_store_mapping()
    return project_key in vector_store_mapping


def get_vector_store_id(project_key):
    """Get vector store ID for a project"""
    vector_store_mapping = get_vector_store_mapping()
    return vector_store_mapping.get(project_key, None)
