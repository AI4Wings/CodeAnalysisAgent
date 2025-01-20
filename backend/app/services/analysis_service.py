from typing import List, Dict, Optional
from langchain.prompts import PromptTemplate
from langchain_openai import ChatOpenAI
from langchain.schema.runnable import RunnablePassthrough
from pydantic import SecretStr
import os
import json
import re
import logging
from dotenv import load_dotenv

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv(verbose=True)

# Verify environment setup
if not os.getenv("OPENAI_API_KEY"):
    logger.error("OpenAI API key not found in environment variables")
    raise EnvironmentError("OPENAI_API_KEY environment variable is required")

class AnalysisError(Exception):
    """Custom exception for analysis errors"""
    pass

class AnalysisService:
    def __init__(self):
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise AnalysisError("OpenAI API key not found. Please set OPENAI_API_KEY environment variable.")
            
        try:
            if not api_key:
                raise ValueError("OpenAI API key is required")
            
            logger.info("Initializing ChatOpenAI with API key")
            self.llm = ChatOpenAI(
                model="gpt-4",
                temperature=0,
                api_key=SecretStr(api_key)
            )
            # Verify the LLM is properly initialized
            if not self.llm:
                raise ValueError("ChatOpenAI initialization failed")
            logger.info("ChatOpenAI initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize ChatOpenAI: {str(e)}")
            raise AnalysisError(f"Failed to initialize ChatOpenAI: {str(e)}")
        
        self.analysis_prompt = PromptTemplate(
            input_variables=["file_name", "file_type", "code_changes", "android_api_changes"],
            template="""Analyze the following code changes from file {file_name} (type: {file_type}) for compatibility issues and semantic changes.
Detected Android API changes: {android_api_changes}

Code changes to analyze:
{code_changes}

Your task is to:
1. Identify any Android API changes that require compatibility testing
2. Analyze security implications, especially for screen sharing and privacy features
3. Evaluate UI/interaction effects
4. Determine testing requirements
5. Provide detailed explanations for ALL sections, even when no impact is detected

Pay special attention to:
- Changes involving Android notification APIs (e.g. setPublicVersion, setContentSensitivity)
- Screen sharing protection features in Android 15+
- Privacy-related modifications and data exposure risks
- API version-specific features and deprecations
- Behavioral changes that might affect user experience

Important: For each section, you MUST:
1. Reference specific lines of code that led to your conclusions using line numbers and exact code snippets
2. Explain why certain impacts are present or absent by connecting code changes to their effects
3. Provide detailed reasoning even when no impact is detected, explaining what was analyzed
4. Format code references as 'Line X: `code_snippet`' when citing specific changes

Examples of good explanations with code references:
- When changes affect compatibility: "Line 797: `.setPublicVersion(publicNotification)` introduces Android 15 screen sharing protection requirements as this API is only available in Android 15+."
- When no UI impact: "The changes (Lines 792-799) only modify notification security settings through `.setPublicVersion()` and `.setContentText()` calls. These methods handle data display policies but do not alter the visual layout or user interaction patterns."
- When no security implications: "The modifications in Lines 757-765 only update UI parameters (`layout_width="match_parent"`, `layout_height="wrap_content"`). These layout changes do not interact with sensitive data or security features."
- When explaining compatibility: "The addition of Line 800: `.setPublicVersion(publicNotification)` requires testing on Android 15+ because this API specifically handles screen sharing protection features introduced in that version."

Format the response as JSON with the following structure (do not include any comments, just pure JSON). Always include line numbers and code snippets in explanations:
{
    "compatibility_testing_required": true/false,
    "compatibility_analysis": {
        "reasoning": "Detailed explanation of why compatibility testing is or is not required, with line numbers and code snippets (e.g., 'Line 123: `method_call()`')",
        "affected_versions": {
            "min_version": "Android version string",
            "target_versions": ["Android version string"],
            "specific_apis": ["API name string"]
        }
    },
    "compatibility_reasons": [
        {
            "feature": "Feature name string",
            "impact": "Detailed impact description with code references",
            "affected_versions": ["Android version string"],
            "severity": "high/medium/low",
            "reasoning": "Explanation of why this feature requires attention"
        }
    ],
    "security_implications": [
        {
            "type": "privacy/security/data_exposure",
            "description": "Detailed description with code references",
            "severity": "high/medium/low",
            "mitigation": "Mitigation steps",
            "reasoning": "Explanation of security impact or why no security concerns exist"
        }
    ],
    "ui_impact": {
        "has_visual_changes": true/false,
        "reasoning": "Detailed explanation of UI impact analysis, including why changes do or do not affect the UI",
        "changes": [
            {
                "component": "Component name",
                "description": "Change description with code references",
                "user_impact": "User impact description"
            }
        ]
    },
    "testing_recommendations": [
        {
            "category": "compatibility/security/ui/performance",
            "description": "Test description with specific scenarios",
            "priority": "high/medium/low",
            "test_environments": ["Environment description"],
            "reasoning": "Explanation of why this test is necessary"
        }
    ]
}"""
        )
        
        # Use RunnableSequence pattern instead of deprecated LLMChain
        self.analysis_chain = self.analysis_prompt | self.llm

    async def analyze_changes(self, repo_info: Dict) -> Dict:
        """Analyze code changes using LangChain."""
        try:
            logger.info(f"Starting analysis for repository: {repo_info.get('repository', 'unknown')}")
            results = []
            
            for change in repo_info.get("files", []):
                if not change.get("patch"):
                    logger.info(f"Skipping file {change.get('filename', 'unknown')} - no patch content")
                    continue
                    
                logger.info(f"Analyzing file: {change.get('filename', 'unknown')}")
                
                analysis_data = None
                try:
                    # Prepare input for analysis
                    analysis_input = {
                        "file_name": change["filename"],
                        "file_type": change.get("file_type", "unknown"),
                        "code_changes": change["patch"],
                        "android_api_changes": json.dumps(change.get("android_api_changes", []), indent=2)
                    }
                    
                    # Run analysis with new RunnableSequence pattern
                    logger.info(f"Running analysis for {change['filename']}")
                    analysis_result = await self.analysis_chain.ainvoke(analysis_input)
                    
                    # Get the content from the analysis result
                    if hasattr(analysis_result, 'content'):
                        analysis_text = analysis_result.content
                    else:
                        analysis_text = str(analysis_result)
                    
                    logger.debug(f"Raw analysis response for {change['filename']}: {analysis_text}")
                    
                    # Try to parse as JSON
                    try:
                        if isinstance(analysis_text, (str, bytes, bytearray)):
                            analysis_data = json.loads(analysis_text)
                        else:
                            analysis_text_str = str(analysis_text)
                            # Try to extract JSON from the text if it's wrapped in other content
                            json_match = re.search(r'\{.*\}', analysis_text_str, re.DOTALL)
                            if json_match:
                                analysis_data = json.loads(json_match.group(0))
                            else:
                                logger.error(f"Failed to parse JSON for {change['filename']}: {analysis_text_str}")
                                raise ValueError("Failed to parse analysis result as JSON")
                    except (json.JSONDecodeError, TypeError) as e:
                        logger.error(f"JSON parsing error for {change['filename']}: {str(e)}")
                        raise ValueError(f"Failed to parse analysis result as JSON: {str(e)}")
                    
                    # Validate the structure of the parsed JSON
                    required_fields = {
                        "compatibility_testing_required": bool,
                        "compatibility_analysis": {
                            "reasoning": str,
                            "affected_versions": {
                                "min_version": str,
                                "target_versions": list,
                                "specific_apis": list
                            }
                        },
                        "compatibility_reasons": list,
                        "security_implications": list,
                        "ui_impact": {
                            "has_visual_changes": bool,
                            "reasoning": str,
                            "changes": list
                        },
                        "testing_recommendations": list
                    }
                    
                    def validate_field(data, schema, path=""):
                        if isinstance(schema, dict):
                            if not isinstance(data, dict):
                                raise ValueError(f"Expected dict at {path}, got {type(data)}")
                            for key, subschema in schema.items():
                                if key not in data: 
                                    raise ValueError(f"Missing required field: {path + '.' if path else ''}{key}")
                                validate_field(data[key], subschema, f"{path + '.' if path else ''}{key}")
                        elif isinstance(schema, type):
                            if not isinstance(data, schema):
                                raise ValueError(f"Invalid type for {path}: expected {schema}, got {type(data)}")
                            # Validate non-empty strings
                            if schema == str and not data.strip():
                                raise ValueError(f"Empty string not allowed for {path}")
                        elif schema == list:
                            if not isinstance(data, list):
                                raise ValueError(f"Expected list at {path}, got {type(data)}")
                    
                    try:
                        validate_field(analysis_data, required_fields)
                    except ValueError as e:
                        logger.error(f"Invalid response structure for {change['filename']}: {str(e)}")
                        raise ValueError(f"Invalid response structure: {str(e)}")
                        
                except Exception as e:
                    logger.error(f"Error processing analysis for {change['filename']}: {str(e)}")
                    analysis_data = {
                        "compatibility_testing_required": False,
                        "compatibility_analysis": {
                            "reasoning": f"Analysis failed: {str(e)}. Unable to determine compatibility requirements.",
                            "affected_versions": {
                                "min_version": "unknown",
                                "target_versions": [],
                                "specific_apis": []
                            }
                        },
                        "compatibility_reasons": [],
                        "security_implications": [],
                        "ui_impact": {
                            "has_visual_changes": False,
                            "reasoning": "Unable to analyze UI impact due to analysis failure.",
                            "changes": []
                        },
                        "testing_recommendations": [],
                        "error": f"Analysis failed: {str(e)}"
                    }
                
                # Always append results, whether analysis succeeded or failed
                results.append({
                    "filename": change["filename"],
                    "analysis": analysis_data,
                    "changes": change
                })
            
            return {
                "repository": repo_info["repository"],
                "commit": repo_info["commit"],
                "files": results
            }
            
        except Exception as e:
            logger.error(f"Analysis process failed: {str(e)}")
            raise AnalysisError(f"Analysis process failed: {str(e)}")
