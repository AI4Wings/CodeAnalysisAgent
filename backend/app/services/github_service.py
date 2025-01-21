from github import Github
from github.GithubException import GithubException, RateLimitExceededException
from typing import List, Dict, Optional
import re
from dotenv import load_dotenv
import os

# Load environment variables
load_dotenv()

class GitHubError(Exception):
    """Custom exception for GitHub-related errors"""
    pass

class GitHubService:
    def __init__(self):
        """Initialize GitHub service with token from environment."""
        # Use GITHUB_TOKEN for authentication
        token = os.getenv("GITHUB_TOKEN")
        if not token:
            raise GitHubError("No GitHub token found. Set GITHUB_TOKEN environment variable.")
            
        # Validate token format
        if not token.startswith(('ghp_', 'github_pat_')):
            raise GitHubError("Invalid token format. Token must start with 'ghp_' or 'github_pat_'")
            
        # Initialize GitHub client with token
        try:
            print(f"Initializing GitHub client with token starting with: {token[:4]}...")
            self.github = Github(token)
            
            # Test token validity with user info
            print("Testing token validity...")
            user = self.github.get_user()
            rate_limit = self.github.get_rate_limit()
            
            print(f"GitHub API initialized successfully!")
            print(f"Authenticated as: {user.login}")
            print(f"Rate limit: {rate_limit.core.remaining}/{rate_limit.core.limit}")
        except GithubException as e:
            if e.status == 401:
                raise GitHubError(f"Invalid token format or expired token. Please check GITHUB_TOKEN value.")
            elif e.status == 403:
                raise GitHubError(f"Token lacks required permissions: {str(e)}")
            else:
                raise GitHubError(f"GitHub API error: {str(e)}")
        except Exception as e:
            raise GitHubError(f"Failed to initialize GitHub client: {str(e)}")

    def _detect_android_api_changes(self, patch: str) -> List[Dict[str, str]]:
        """Detect Android API changes in the patch."""
        if not patch:
            return []
            
        api_changes = []
        android_api_patterns = [
            (r'\.setPublicVersion\s*\(', 'Android 15 - Screen sharing protection'),
            (r'\.setContentSensitivity\s*\(', 'Android 15 - Content sensitivity'),
            (r'\.setVisibility\s*\(\s*NotificationCompat\.VISIBILITY_', 'Notification visibility'),
            (r'\.setCategory\s*\(\s*NotificationCompat\.CATEGORY_', 'Notification category')
        ]
        
        for pattern, description in android_api_patterns:
            if re.search(pattern, patch):
                api_changes.append({
                    "api": pattern.split(r'\.')[-1].split(r'\(')[0],
                    "description": description
                })
                
        return api_changes

    def parse_commit_url(self, url: str) -> Optional[Dict[str, str]]:
        """Parse GitHub commit URL to extract owner, repo, and commit hash."""
        pattern = r"https://github\.com/([^/]+)/([^/]+)/commit/([a-f0-9]+)"
        match = re.match(pattern, url)
        
        if not match:
            return None
            
        return {
            "owner": match.group(1),
            "repo": match.group(2),
            "commit_hash": match.group(3)
        }

    def get_commit_changes(self, url: str) -> Dict:
        """Get the changes from a specific commit."""
        try:
            parsed = self.parse_commit_url(url)
            if not parsed:
                raise GitHubError("Invalid GitHub commit URL format")

            repo = self.github.get_repo(f"{parsed['owner']}/{parsed['repo']}")
            commit = repo.get_commit(parsed['commit_hash'])
            
            # Get repository and commit information
            repo_info = {
                "repository": f"{parsed['owner']}/{parsed['repo']}",
                "commit": parsed['commit_hash'],
                "files": []
            }
            changes = []
            for file in commit.files:
                # Skip binary files and files without patches
                if not file.patch:
                    continue
                    
                # Detect file type and Android-specific files
                is_android_file = (
                    file.filename.endswith('.java') and
                    ('/android/' in file.filename.lower() or
                    'app/src/main' in file.filename)
                )
                
                file_type = (
                    'java' if file.filename.endswith('.java')
                    else 'kotlin' if file.filename.endswith('.kt')
                    else 'xml' if file.filename.endswith('.xml')
                    else 'other'
                )
                
                changes.append({
                    "filename": file.filename,
                    "status": file.status,
                    "additions": file.additions,
                    "deletions": file.deletions,
                    "changes": file.changes,
                    "patch": file.patch,
                    "is_android_file": is_android_file,
                    "file_type": file_type,
                    "android_api_changes": self._detect_android_api_changes(file.patch) if is_android_file else []
                })
            
            repo_info["files"] = changes
            return repo_info
            
        except RateLimitExceededException:
            raise GitHubError("GitHub API rate limit exceeded. Please try again later.")
        except GithubException as e:
            raise GitHubError(f"GitHub API error: {str(e)}")
        except Exception as e:
            raise GitHubError(f"Error fetching commit changes: {str(e)}")
