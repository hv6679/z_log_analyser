"""
Utility functions for log analysis application
Handles file operations, text extraction, PDF conversion, and log type detection
"""

import io
import os
import tempfile
import re
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import inch
import streamlit as st


def extract_text_from_file(uploaded_file):
    """Extract text content from various file types"""
    try:
        # Handle BytesIO objects (from JIRA attachments)
        if isinstance(uploaded_file, io.BytesIO):
            uploaded_file.seek(0)  # Reset position to beginning
            content = uploaded_file.read()
            uploaded_file.seek(0)  # Reset position again for future reads
            
            # Check if it might be a PDF by looking at file header
            if content.startswith(b'%PDF'):
                return _extract_pdf_text(uploaded_file)
            
            # Try to decode as UTF-8 text
            return _decode_text_content(content)
        
        # Handle regular uploaded files
        if hasattr(uploaded_file, 'type'):
            if uploaded_file.type == "application/pdf":
                return _extract_pdf_text_from_bytes(uploaded_file.getvalue())
            elif uploaded_file.type in ['text/plain', 'text/csv', 'application/json']:
                return uploaded_file.getvalue().decode('utf-8')
            else:
                # Try to decode as text for other file types
                try:
                    return uploaded_file.getvalue().decode('utf-8')
                except UnicodeDecodeError:
                    st.warning(f" Could not decode {uploaded_file.type} as text")
                    return ""
        else:
            # Fallback: try to read as bytes and decode
            return _fallback_text_extraction(uploaded_file)
            
    except Exception as e:
        st.warning(f" Error extracting text: {str(e)}")
        return ""


def _extract_pdf_text(file_obj):
    """Extract text from PDF file object"""
    try:
        import PyPDF2
        file_obj.seek(0)
        pdf_reader = PyPDF2.PdfReader(file_obj)
        text = ""
        for page in pdf_reader.pages:
            text += page.extract_text() + "\n"
        file_obj.seek(0)  # Reset position
        return text
    except ImportError:
        st.warning(" PyPDF2 not installed. Install it with: pip install PyPDF2")
        return ""
    except Exception as e:
        st.warning(f" Could not extract text from PDF attachment: {str(e)}")
        return ""


def _extract_pdf_text_from_bytes(pdf_bytes):
    """Extract text from PDF bytes"""
    try:
        import PyPDF2
        pdf_reader = PyPDF2.PdfReader(io.BytesIO(pdf_bytes))
        text = ""
        for page in pdf_reader.pages:
            text += page.extract_text() + "\n"
        return text
    except ImportError:
        st.warning(" PyPDF2 not installed. Install it with: pip install PyPDF2")
        return ""
    except Exception as e:
        st.warning(f" Could not extract text from PDF: {str(e)}")
        return ""


def _decode_text_content(content):
    """Decode text content with multiple encoding attempts"""
    try:
        return content.decode('utf-8')
    except UnicodeDecodeError:
        # Try other common encodings
        for encoding in ['latin-1', 'cp1252', 'iso-8859-1']:
            try:
                return content.decode(encoding)
            except UnicodeDecodeError:
                continue
        st.warning(" Could not decode attachment as text with any common encoding")
        return ""


def _fallback_text_extraction(uploaded_file):
    """Fallback method for text extraction"""
    try:
        if hasattr(uploaded_file, 'getvalue'):
            content = uploaded_file.getvalue()
        elif hasattr(uploaded_file, 'read'):
            content = uploaded_file.read()
            uploaded_file.seek(0)  # Reset position
        else:
            st.warning(" Unknown file object type")
            return ""
        
        if isinstance(content, bytes):
            return content.decode('utf-8')
        else:
            return str(content)
    except Exception as e:
        st.warning(f" Could not extract text from file: {str(e)}")
        return ""


def convert_to_pdf(uploaded_file):
    """Convert any file to PDF format"""
    try:
        # If it's already a PDF, return as is
        if hasattr(uploaded_file, 'type') and uploaded_file.type == "application/pdf":
            return uploaded_file.getvalue(), uploaded_file.name
        
        # Extract text content first
        text_content = extract_text_from_file(uploaded_file)
        if hasattr(uploaded_file, 'seek'):
            uploaded_file.seek(0)  # Reset file pointer
        
        if not text_content:
            # If we can't extract text, create a PDF with filename info
            text_content = f"Log file: {uploaded_file.name}\nContent could not be extracted as text."
        
        # Create PDF from text content
        pdf_buffer = io.BytesIO()
        doc = SimpleDocTemplate(
            pdf_buffer, 
            pagesize=letter, 
            leftMargin=0.75*inch, 
            rightMargin=0.75*inch,
            topMargin=0.75*inch, 
            bottomMargin=0.75*inch
        )
        
        styles = getSampleStyleSheet()
        story = []
        
        # Add title
        title = Paragraph(f"<b>Log File: {uploaded_file.name}</b>", styles['Title'])
        story.append(title)
        story.append(Spacer(1, 0.2*inch))
        
        # Split content into paragraphs and add to PDF
        paragraphs = text_content.split('\n')
        for para in paragraphs:
            if para.strip():  # Only add non-empty paragraphs
                # Escape special characters for reportlab
                para_escaped = para.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
                p = Paragraph(para_escaped, styles['Normal'])
                story.append(p)
                story.append(Spacer(1, 0.1*inch))
        
        doc.build(story)
        pdf_data = pdf_buffer.getvalue()
        pdf_buffer.close()
        
        # Generate PDF filename
        base_name = os.path.splitext(uploaded_file.name)[0]
        pdf_name = f"{base_name}_converted.pdf"
        
        return pdf_data, pdf_name
        
    except Exception as e:
        st.error(f"Error converting file to PDF: {str(e)}")
        return None, None


def detect_log_type(content):
    """Detect if the log is Windows logs or ADB logs"""
    if not content or len(content.strip()) == 0:
        return "unknown"
        
    # ADB/Android log indicators - comprehensive patterns
    adb_indicators = [
        "adb:", "logcat", "ActivityManager", "WindowManager", 
        "dalvikvm", "AndroidRuntime", "System.err",
        "I/", "D/", "V/", "W/", "E/",  # Android log level prefixes
        "ActivityTaskManager", "CoreBackPreview", "WindowManagerShell",
        "PackageManager", "AppsFilter", "ActivityThread",
        "BackupManagerService", "LauncherAppsService",
        "com.android.", "android.intent", "android.app.",
        "PackageSetting", "ComponentInfo", "TransitionRequestInfo"
    ]
    
    windows_indicators = [
        "Event ID", "Source:", "Level:", "Task Category:", "Keywords:",
        "Microsoft-Windows", "Application Error", "System Error", 
        "Warning", "Information", "Error", "Critical", "Section start", "Exit status",
        "[Exit status: SUCCESS]", "[Exit status: FAILURE]", "Section start:",
        "Windows", "Driver", "Installation", "Registry", "System32", "Program Files",
        "EventLog", "Service", "Process", "Thread", "Module", "Device Manager",
        "Setup", "Install", "Uninstall", "Update", "Patch"
    ]
    
    content_lower = content.lower()
    
    # Calculate basic scores
    adb_score = sum(1 for indicator in adb_indicators if indicator.lower() in content_lower)
    windows_score = sum(1 for indicator in windows_indicators if indicator.lower() in content_lower)
    
    # Add pattern-based scoring
    adb_score += _calculate_android_patterns(content)
    windows_score += _calculate_windows_patterns(content_lower)
        
    # Determine log type based on scores
    if adb_score > windows_score:
        return "adb"
    elif windows_score > adb_score:
        return "windows"
    else:
        return "unknown"


def _calculate_android_patterns(content):
    """Calculate Android-specific pattern scores"""
    score = 0
    
    # Check for Android timestamp pattern (MM-dd HH:mm:ss.SSS)
    android_timestamp_pattern = r'\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2}\.\d{3}'
    if re.search(android_timestamp_pattern, content):
        score += 10  # Very strong indicator for Android logs
    
    # Check for Android log level patterns (like "I/ActivityManager", "D/CoreBackPreview")
    android_log_pattern = r'[VDIWEF]\/\w+'
    android_matches = len(re.findall(android_log_pattern, content))
    score += android_matches * 2  # Each match adds significant weight
    
    # Check for Android package names pattern
    content_lower = content.lower()
    if any(pkg in content_lower for pkg in ["com.zebra.", "com.android.", "com.google.android."]):
        score += 8  # Strong Android indicator
        
    return score


def _calculate_windows_patterns(content_lower):
    """Calculate Windows-specific pattern scores"""
    score = 0
    
    # Add additional scoring for specific patterns
    if "section start" in content_lower and "exit status" in content_lower:
        score += 5  # Strong indicator for Windows logs with sections
        
    return score


def create_temp_pdf_file(pdf_data):
    """Create a temporary PDF file and return the path"""
    temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".pdf")
    temp_file.write(pdf_data)
    temp_file.close()
    return temp_file.name


def cleanup_temp_files(*file_paths):
    """Clean up multiple temporary files"""
    for file_path in file_paths:
        try:
            if file_path and os.path.exists(file_path):
                os.unlink(file_path)
        except Exception:
            pass  # Ignore cleanup errors


def get_analysis_prompt(detected_log_type, bug_description="", custom_prompt=""):
    """Get the appropriate analysis prompt based on log type"""
    if detected_log_type == "windows":
        return "Analyze these log sections with exit status failure and give me the reason for the failure in that sections , and give a small summary of what is happening in every section with appropriate heading without any greetings"
    elif detected_log_type == "adb":
        if bug_description:
            return f" for the given bug description: {bug_description} Analyze these ADB logs for the application. Identify the error that caused this bug, for these errors go and identify what part of the source code (given in context) which is causing the error and highlight it and try to give a possible fix for this issue."
        else:
            return "Analyze these ADB logs for the application. Identify all the errors that were caused and for these errors give me a possible fix "
    else:
        return custom_prompt or "Analyse this log file and give me a error summary"
