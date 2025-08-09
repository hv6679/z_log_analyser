"""
Main Streamlit application for Log Analyzer
Combines utilities and JIRA integration for AI-powered log analysis
"""

import streamlit as st
import tempfile
import os
import traceback
from openai import OpenAI
import streamlit_mermaid as stmd

OPENAI_API_KEY = st.secrets["openai_api_key"]

# Import our utility modules
from utils import (
    extract_text_from_file, convert_to_pdf, detect_log_type, 
    create_temp_pdf_file, cleanup_temp_files, get_analysis_prompt
)
from jira_utils import (
    get_jira_projects, get_bugs_from_project, get_bug_description, 
    get_bug_attachments, download_attachment, is_project_supported, get_vector_store_id
)


# Configure Streamlit page
st.set_page_config(
    page_title="Log Analyzer 📝",
    page_icon="📝",
    layout="wide"
)

st.title("🔍 Log Analyzer")
st.markdown("**Upload your log file and get AI-powered analysis with source code context**")


# Initialize OpenAI client
@st.cache_resource
def get_openai_client():
    return OpenAI(
        api_key=OPENAI_API_KEY
    )


def setup_sidebar():
    """Setup sidebar configuration and JIRA integration"""
    st.sidebar.header("⚙️ Configuration")
    st.sidebar.header(" JIRA Integration")

    # Initialize variables
    bug_description = ""
    attached_file = None
    vector_store_id = None

    # Fetch JIRA projects
    with st.spinner("🔄 Loading JIRA projects..."):
        jira_projects = get_jira_projects()

    if jira_projects:
        # JIRA Project selection
        project_options = ["Select a project"] + [f"{proj['key']} - {proj['name']}" for proj in jira_projects]
        selected_jira_project = st.sidebar.selectbox(
            "Select JIRA Project",
            project_options,
            help="Choose a JIRA project to fetch bugs from"
        )
        
        # Extract project key from selection
        if selected_jira_project != "Select a project":
            selected_project_key = selected_jira_project.split(" - ")[0]
            st.sidebar.info(f"✅ Selected Project: **{selected_project_key}**")
            
            # Check if project is supported
            if is_project_supported(selected_project_key):
                vector_store_id = get_vector_store_id(selected_project_key)
                st.sidebar.success(f"**{selected_project_key}** is a supported project for this tool!")
                tool_supported = True
            else:
                vector_store_id = None
                tool_supported = False
                st.sidebar.error(f"This tool is not supported for project **{selected_project_key}**")
                st.sidebar.warning("⚠️ Please contact the administrator to add vector store support for this project.")
            
            # Only proceed with bug fetching if tool is supported
            if tool_supported:
                bug_description, attached_file = handle_bug_selection(selected_project_key)
        else:
            selected_project_key = None
            bug_description = ""
            attached_file = None
    else:
        st.sidebar.error("❌ Could not load JIRA projects. Check your connection and credentials.")
        selected_project_key = None
        bug_description = ""
        attached_file = None

    return bug_description, attached_file, vector_store_id


def handle_bug_selection(selected_project_key):
    """Handle bug selection and attachment download"""
    bug_description = ""
    attached_file = None

    # Fetch bugs from selected project
    with st.sidebar:
        with st.spinner(f"🔄 Loading {selected_project_key} bugs... Please wait"):
            project_bugs = get_bugs_from_project(selected_project_key)
    if project_bugs:
        # Bug selection dropdown
        bug_options = ["Select a bug"] + [f"{bug['key']} - {bug['summary'][:50]}{'...' if len(bug['summary']) > 50 else ''}" for bug in project_bugs]
        selected_bug = st.sidebar.selectbox(
            f"Select Bug from {selected_project_key}",
            bug_options,
            help="Choose a specific bug to analyze"
        )
        
        # Extract bug key from selection
        if selected_bug != "Select a bug":
            selected_bug_key = selected_bug.split(" - ")[0]
            st.sidebar.success(f"✅ Selected Bug: **{selected_bug_key}**")
            
            # Fetch and display bug description
            with st.spinner(f"Loading bug details for {selected_bug_key}..."):
                bug_details = get_bug_description(selected_bug_key)
            
            if bug_details:
                # Save description to variable
                bug_description = bug_details['description']
                
                st.sidebar.markdown("### 📝 Bug Details")
                st.sidebar.markdown(f"**Status:** {bug_details['status']}")
                st.sidebar.markdown(f"**Priority:** {bug_details['priority']}")
                st.sidebar.markdown(f"**Assignee:** {bug_details['assignee']}")
                
                with st.sidebar.expander("📝 Bug Description", expanded=False):
                    st.markdown(f"{bug_details['description']}")
                
                # Handle attachments
                attached_file = handle_attachments(selected_bug_key)
    else:
        st.sidebar.warning("⚠️ No bugs found in this project")

    return bug_description, attached_file


def handle_attachments(selected_bug_key):
    """Handle bug attachments selection and download"""
    attached_file = None
    
    # Fetch and display attachments
    with st.spinner(f"📎 Loading attachments for {selected_bug_key}..."):
        bug_attachments = get_bug_attachments(selected_bug_key)
    
    if bug_attachments:
        st.sidebar.markdown("### 📎 Log Attachments")
        attachment_options = ["No attachment"] + [f"{att['filename']} ({att['size']} bytes)" for att in bug_attachments]
        selected_attachment = st.sidebar.selectbox(
            "Select Log Attachment",
            attachment_options,
            help="Choose a log attachment from the bug"
        )
        
        if selected_attachment != "No attachment":
            # Find the selected attachment
            selected_att_filename = selected_attachment.split(" (")[0]
            selected_att = next((att for att in bug_attachments if att['filename'] == selected_att_filename), None)
            
            if selected_att:
                st.sidebar.success(f"✅ Selected: **{selected_att['filename']}**")
                # Download the attachment
                with st.spinner(f"⬇️ Downloading {selected_att['filename']}..."):
                    attached_file = download_attachment(selected_att['id'], selected_att['filename'])
                if attached_file:
                    st.sidebar.success("📥 Attachment downloaded successfully!")
                else:
                    st.sidebar.error("❌ Failed to download attachment")
    else:
        st.sidebar.info("ℹ️ No log attachments found in this bug")
    
    return attached_file


def setup_model_configuration():
    """Setup model configuration in sidebar"""
    st.sidebar.markdown("---")
    st.sidebar.header("🤖 Model Configuration")
    model_name = st.sidebar.selectbox(
        " Select Model",
        ["gpt-4.1", "gpt-4", "gpt-3.5-turbo"],
        index=0
    )
    # Custom analysis prompt
    default_prompt = "Analyse this log file and give me an error summary"
    analysis_prompt = st.sidebar.text_area(
        "📝 Custom Analysis Prompt (for unknown log types)",
        value=default_prompt,
        height=150,
        help="This prompt will be used for unknown log types. Windows and ADB logs have specialized prompts."
    )
    # Show analysis modes info
    st.sidebar.markdown("### 🔎 Analysis Modes")
    st.sidebar.markdown("""
    **🪟 Windows Logs:**
    - Analyzes failure sections
    - Identifies exit status failures
    - Summarizes each section

    **🤖 ADB Logs:**
    - Specific error analysis for JIRA issues
    - Provides possible fixes for your source code
    - User flow diagram generation

    **❓ Unknown Logs:**
    - Uses custom prompt above
    - General error analysis
    """)

    return model_name, analysis_prompt


def process_files_for_analysis(files_to_analyze, client):
    """Process files and upload them for analysis"""
    file_ids = []
    temp_file_paths = []
    
    try:
        for source, file_obj in files_to_analyze:
            with st.spinner(f" Processing {source.lower()} file..."):
                # Convert file to PDF
                pdf_data, pdf_name = convert_to_pdf(file_obj)
                if hasattr(file_obj, 'seek'):
                    file_obj.seek(0)  # Reset file pointer
                
                if pdf_data is None:
                    st.error(f" Failed to process {source.lower()} file")
                    continue
                
                # Create a temporary PDF file
                temp_file_path = create_temp_pdf_file(pdf_data)
                temp_file_paths.append(temp_file_path)
                
                # Upload PDF file to OpenAI
                with open(temp_file_path, "rb") as file_obj_upload:
                    file_uploaded = client.files.create(
                        file=file_obj_upload,
                        purpose="user_data"
                    )
                file_ids.append(file_uploaded.id)
                st.success(f"✅ {file_obj.name} processed and uploaded for Analysis")
        
        return file_ids, temp_file_paths
    
    except Exception as e:
        st.error(f" Error processing files: {str(e)}")
        # Cleanup on error
        cleanup_temp_files(*temp_file_paths)
        return [], []


def perform_ai_analysis(file_ids, files_to_analyze, bug_description, analysis_prompt, model_name, vector_store_id, client):
    """Perform AI analysis on the uploaded files"""
    with st.spinner(" Analyzing log file with AI..."):
        # Determine which file to use for log type detection
        file_for_detection = files_to_analyze[0][1]  # Use the first file
        
        # Detect log type from the file
        try:
            content = extract_text_from_file(file_for_detection)
            if hasattr(file_for_detection, 'seek'):
                file_for_detection.seek(0)  # Reset file pointer if possible
            
            if content:
                detected_log_type = detect_log_type(content)
            else:
                detected_log_type = "unknown"
                st.warning(" Could not extract text for log type detection, using default analysis")
        except Exception as e:
            detected_log_type = "unknown"
            st.warning(f" Error during log type detection: {str(e)}, using default analysis")
        
        # Get analysis prompt based on detected log type
        analysis_text = get_analysis_prompt(detected_log_type, bug_description, analysis_prompt)
        
        # Display log type detection result
        if detected_log_type == "adb":
            st.success("🤖 Using ADB log analysis mode")
        elif detected_log_type == "windows":
            st.success("🪟 Using Windows log analysis mode")
        else:
            st.info("🔍 Using general log analysis mode")

        # Create input files list for the API request
        input_files = []
        for file_id in file_ids:
            input_files.append({
                "type": "input_file",
                "file_id": file_id,
            })
        
        # Add the analysis text
        input_files.append({
            "type": "input_text",
            "text": analysis_text,
        })
        
        # Create the analysis request
        if vector_store_id is not None:
            response = client.responses.create(
                model=model_name,
                tools=[{"type": "file_search", "vector_store_ids": [vector_store_id]}],
                input=[
                    {
                        "role": "user",
                        "content": input_files
                    }
                ]
            )
        else:
            response = client.responses.create(
                model=model_name,
                input=[
                    {
                        "role": "user",
                        "content": input_files
                    }
                ]
            )

        return response, detected_log_type


def display_analysis_results(response, detected_log_type, file_ids, client):
    """Display the analysis results"""
    st.subheader(" Analysis Results")
    
    if hasattr(response, 'output_text') and response.output_text:
        st.markdown("###  AI Analysis")
        st.markdown(response.output_text)
    elif hasattr(response, 'output') and response.output:
        st.markdown("###  AI Analysis")
        # Handle different response formats
        if isinstance(response.output, list) and len(response.output) > 0:
            for i, output_item in enumerate(response.output):
                if hasattr(output_item, 'content') and output_item.content:
                    for content_item in output_item.content:
                        if hasattr(content_item, 'text'):
                            st.markdown(content_item.text)
        else:
            st.write(response.output)
    else:
        st.error(" No analysis output received from the API")
        st.json(dict(response))  # Debug output

    # Generate mermaid diagram for ADB logs
    if detected_log_type == "adb" and file_ids:
        generate_user_flow_diagram(file_ids, client)


def generate_user_flow_diagram(file_ids, client):
    """Generate user flow diagram for ADB logs"""
    try:
        st.subheader(" User Flow Diagram")
        with st.spinner("Generating user flow diagram..."):
            mermaid_response = client.responses.create(
                model="gpt-4.1",
                input=[
                    {
                        "role": "user",
                        "content": [{
                            "type": "input_text",
                            "text": "now based on the log file context I want you to generate only an error-free mermaid code with semicolons (sequenceDiagram) for the user flow events that has occurred when the user used the app for this instance and what exactly happened in the UI, ignore generic logs, and nothing else, give me the output in a single line and add semicolons wherever required",
                        }, {
                            "type": "input_file",
                            "file_id": file_ids[0],
                        }]
                    }
                ]
            )

            if hasattr(mermaid_response, 'output_text'):
                mermaid_code = mermaid_response.output_text
                mermaid_code = mermaid_code.replace("`", "").replace("mermaid", "")
                stmd.st_mermaid(mermaid_code, key="logs")
            else:
                st.warning("Could not generate user flow diagram")
    except Exception as e:
        st.warning(f"Error generating user flow diagram: {str(e)}")


def main():
    """Main application function"""
    client = get_openai_client()
    
    # Setup sidebar
    bug_description, attached_file, vector_store_id = setup_sidebar()
    model_name, analysis_prompt = setup_model_configuration()

    # Main content area
    col1, col2 = st.columns([1, 2])

    with col1:

        st.header("📁 Upload Log File")
        uploaded_file = st.file_uploader(
            "Choose a log file",
            type=['txt', 'log', 'pdf', 'csv', 'json'],
            help="Supported formats: TXT, LOG, PDF, CSV, JSON"
        )
        # Display file information
        files_to_analyze = []
        if uploaded_file is not None:
            files_to_analyze.append(("Uploaded", uploaded_file))
        if attached_file is not None:
            files_to_analyze.append(("Attached", attached_file))
        if files_to_analyze:
            st.subheader("📄 Files to Analyze")
            for source, file_obj in files_to_analyze:
                st.success(f"✅ **{source} file:** {file_obj.name}")
                st.info(f"📏 **File size:** {file_obj.size:,} bytes")
                if hasattr(file_obj, 'type'):
                    st.info(f"🗂️ **File type:** {file_obj.type}")
            # Extract text and detect log type from the first file for display
            try:
                primary_file = files_to_analyze[0][1]
                content = extract_text_from_file(primary_file)
                if hasattr(primary_file, 'seek'):
                    primary_file.seek(0)
                if content:
                    detected_log_type = detect_log_type(content)
                    # Show log type detection result
                    if detected_log_type == "adb":
                        st.success("🤖 **Detected: ADB Logs**")
                    elif detected_log_type == "windows":
                        st.success("🪟 **Detected: Windows Logs**")
                    else:
                        st.warning("❓ **Detected: Unknown Log Type**")
                else:
                    st.warning("⚠️ Could not extract text content for log type detection")
            except Exception as e:
                st.error(f"❌ Error during log type detection: {str(e)}")

    with col2:
        st.header("💡 Analysis")
        if st.button("↪ Analyze Log File", type="secondary", use_container_width=True):
            if not files_to_analyze:
                st.error("❌ No files were available for analysis")
                return
            # Process files for analysis
            file_ids, temp_file_paths = process_files_for_analysis(files_to_analyze, client)
            if not file_ids:
                st.error("❌ No files were successfully processed")
                return
            try:
                # Perform AI analysis
                response, detected_log_type = perform_ai_analysis(
                    file_ids, files_to_analyze, bug_description, 
                    analysis_prompt, model_name, vector_store_id, client
                )
                # Display results
                display_analysis_results(response, detected_log_type, file_ids, client)
            finally:
                # Clean up temporary files
                cleanup_temp_files(*temp_file_paths)
        else:
            # Only show the message if no files are available
            if not files_to_analyze:
                st.info("ℹ️ Please upload a log file to start analysis")

    # Additional information
    st.markdown("---")
    st.markdown("### ℹ️ How to Use")
    st.markdown("""
    1. **Select your Jira issue** and pick the log attachments if any from the ticket
    2. **Upload your log file** using the file picker on the left
    3. **Click 'Analyze Log File'** to get AI-powered analysis
    4. **Review the results** which will include error identification and potential fixes

    **Note:** You can also perform Log analysis for your ADB/Windows Logs without any JIRA ticket—just upload the log file and click 'Analyze Log File'.

    **Supported File Types:** TXT, LOG, PDF, CSV, JSON
    """)

    st.markdown("### ✨ Features")
    st.markdown("""
    - **Source Code Context:** Uses vector store for intelligent analysis with code context
    - **Multiple File Formats:** Supports various log file formats
    - **User Flow Diagram:** Generates a visual representation of user interactions
    - **Model Selection:** Choose from different OpenAI models
    - **Real-time Analysis:** Get instant results with fixes for your bugs
    """)

    # Footer
    st.markdown("---")
    st.markdown("*Developed and Deployed by Mobile CAT IDC for project support and other inquiries [contact us](mailto:hv6679@zebra.com)*")


if __name__ == "__main__":
    main()
