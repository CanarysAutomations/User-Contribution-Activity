import os
import csv
import time
from datetime import datetime, timedelta, timezone
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from dotenv import load_dotenv

# Load .env values
load_dotenv()
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
ORG_NAMES = [org.strip() for org in os.getenv("ORG_NAMES", "").split(",")]
THRESHOLD_DAYS = int(os.getenv("DAYS_INACTIVE_THRESHOLD", "60"))

GRAPHQL_URL = "https://api.github.com/graphql"
HEADERS = {"Authorization": f"Bearer {GITHUB_TOKEN}"}
RATE_DELAY = 3  # Increased delay to reduce connection pressure
REQUEST_TIMEOUT = 30  # Timeout in seconds

# Create session with retry logic
def create_session():
    session = requests.Session()
    retry_strategy = Retry(
        total=5,  # Maximum number of retries
        backoff_factor=2,  # Wait 2, 4, 8, 16, 32 seconds between retries
        status_forcelist=[429, 500, 502, 503, 504],  # HTTP codes to retry
        allowed_methods=["POST"],  # Retry POST requests
        raise_on_status=False
    )
    adapter = HTTPAdapter(max_retries=retry_strategy)
    session.mount("https://", adapter)
    session.mount("http://", adapter)
    return session

SESSION = create_session()

def run_query(query, variables=None, max_attempts=3):
    """Execute GraphQL query with retry logic and error handling"""
    for attempt in range(max_attempts):
        try:
            response = SESSION.post(
                GRAPHQL_URL, 
                json={"query": query, "variables": variables}, 
                headers=HEADERS,
                timeout=REQUEST_TIMEOUT
            )
            if response.status_code == 200:
                return response.json()["data"]
            elif response.status_code == 403:
                print(f"   ⚠️  Rate limit or permission issue. Waiting 60 seconds...")
                time.sleep(60)
                continue
            else:
                print(f"   ⚠️  Query failed with status {response.status_code}. Attempt {attempt + 1}/{max_attempts}")
                if attempt < max_attempts - 1:
                    time.sleep(5 * (attempt + 1))  # Exponential backoff
                    continue
                else:
                    raise Exception(f"GraphQL query failed after {max_attempts} attempts: {response.status_code} - {response.text}")
        except (requests.exceptions.ConnectionError, requests.exceptions.Timeout) as e:
            print(f"   ⚠️  Network error: {str(e)[:100]}. Attempt {attempt + 1}/{max_attempts}")
            if attempt < max_attempts - 1:
                wait_time = 5 * (2 ** attempt)  # Exponential backoff: 5, 10, 20 seconds
                print(f"   ⏳ Waiting {wait_time} seconds before retry...")
                time.sleep(wait_time)
            else:
                print(f"   ❌ Failed after {max_attempts} attempts. Skipping this query.")
                return None
        except Exception as e:
            print(f"   ❌ Unexpected error: {str(e)[:100]}")
            if attempt < max_attempts - 1:
                time.sleep(5 * (attempt + 1))
            else:
                return None
    return None

def later(ts1, ts2):
    if not ts1: return ts2
    if not ts2: return ts1
    return max(ts1, ts2)

def get_all_org_members(org):
    users, cursor = set(), None
    while True:
        query = """
        query($org: String!, $cursor: String) {
          organization(login: $org) {
            membersWithRole(first: 100, after: $cursor) {
              pageInfo { hasNextPage endCursor }
              nodes { login }
            }
          }
        }
        """
        variables = {"org": org, "cursor": cursor}
        result = run_query(query, variables)
        if not result or "organization" not in result:
            print(f"   ⚠️  Failed to fetch members for {org}")
            break
        data = result["organization"]["membersWithRole"]
        users.update([user["login"] for user in data["nodes"]])
        if not data["pageInfo"]["hasNextPage"]:
            break
        cursor = data["pageInfo"]["endCursor"]
        time.sleep(RATE_DELAY)
    return users

def get_all_repos(org):
    repos, cursor = [], None
    while True:
        query = """
        query($org: String!, $cursor: String) {
          organization(login: $org) {
            repositories(first: 100, isFork: false, after: $cursor) {
              pageInfo { endCursor hasNextPage }
              nodes { name }
            }
          }
        }
        """
        variables = {"org": org, "cursor": cursor}
        result = run_query(query, variables)
        if not result or "organization" not in result:
            print(f"   ⚠️  Failed to fetch repositories for {org}")
            break
        data = result["organization"]["repositories"]
        repos.extend([r["name"] for r in data["nodes"]])
        if not data["pageInfo"]["hasNextPage"]:
            break
        cursor = data["pageInfo"]["endCursor"]
        time.sleep(RATE_DELAY)
    return repos

def get_branches(org, repo):
    branches, cursor = [], None
    while True:
        query = """
        query($org: String!, $repo: String!, $cursor: String) {
          repository(owner: $org, name: $repo) {
            refs(refPrefix: "refs/heads/", first: 100, after: $cursor) {
              pageInfo { hasNextPage endCursor }
              nodes { name }
            }
          }
        }
        """
        variables = {"org": org, "repo": repo, "cursor": cursor}
        result = run_query(query, variables)
        if not result or "repository" not in result or not result["repository"]:
            print(f"   ⚠️  Failed to fetch branches for {repo}")
            break
        refs = result["repository"]["refs"]
        branches.extend([b["name"] for b in refs["nodes"]])
        if not refs["pageInfo"]["hasNextPage"]:
            break
        cursor = refs["pageInfo"]["endCursor"]
        time.sleep(RATE_DELAY)
    return branches or ["main"]

def get_commit_activity(org, repo, branch):
    user_activity, cursor = {}, None
    while True:
        query = """
        query($org: String!, $repo: String!, $branch: String!, $cursor: String) {
          repository(owner: $org, name: $repo) {
            ref(qualifiedName: $branch) {
              target {
                ... on Commit {
                  history(first: 100, after: $cursor) {
                    pageInfo { hasNextPage endCursor }
                    edges {
                      node {
                        committedDate
                        author {
                          user { login }
                        }
                      }
                    }
                  }
                }
              }
            }
          }
        }
        """
        variables = {
            "org": org,
            "repo": repo,
            "branch": f"refs/heads/{branch}",
            "cursor": cursor
        }
        result = run_query(query, variables)
        
        # Handle cases where repository or branch doesn't exist
        if not result or not result.get("repository"):
            print(f"   ⚠️  Repository not found or inaccessible: {repo}")
            break
        
        ref = result["repository"].get("ref")
        if not ref or not ref.get("target"):
            print(f"   ⚠️  Branch not found: {branch}")
            break
        
        history = ref["target"].get("history", {})
        for edge in history.get("edges", []):
            author = edge["node"]["author"]["user"]
            if author:
                login = author["login"]
                committed = edge["node"]["committedDate"]
                if login not in user_activity:
                    user_activity[login] = {"commits": 0, "last_commit": committed}
                user_activity[login]["commits"] += 1
                user_activity[login]["last_commit"] = later(user_activity[login]["last_commit"], committed)
        if not history.get("pageInfo", {}).get("hasNextPage"):
            break
        cursor = history["pageInfo"]["endCursor"]
        time.sleep(RATE_DELAY)
    return user_activity

def get_issue_activity(org, repo):
    user_activity, cursor = {}, None
    while True:
        query = """
        query($org: String!, $repo: String!, $cursor: String) {
          repository(owner: $org, name: $repo) {
            issues(first: 100, after: $cursor, orderBy: {field: CREATED_AT, direction: DESC}) {
              pageInfo { hasNextPage endCursor }
              nodes {
                createdAt
                author { login }
              }
            }
          }
        }
        """
        result = run_query(query, {"org": org, "repo": repo, "cursor": cursor})
        if not result or "repository" not in result:
            print(f"   ⚠️  Failed to fetch issues for {repo}")
            break
        issues = result["repository"]["issues"]
        for issue in issues["nodes"]:
            author = issue["author"]
            if author and author.get("login"):
                login = author["login"]
                created = issue["createdAt"]
                if login not in user_activity:
                    user_activity[login] = {"issues": 0, "last_issue": created}
                user_activity[login]["issues"] += 1
                user_activity[login]["last_issue"] = later(user_activity[login]["last_issue"], created)
        if not issues["pageInfo"]["hasNextPage"]:
            break
        cursor = issues["pageInfo"]["endCursor"]
        time.sleep(RATE_DELAY)
    return user_activity

def get_pr_activity(org, repo):
    user_activity, cursor = {}, None
    while True:
        query = """
        query($org: String!, $repo: String!, $cursor: String) {
          repository(owner: $org, name: $repo) {
            pullRequests(first: 100, after: $cursor, orderBy: {field: CREATED_AT, direction: DESC}) {
              pageInfo { hasNextPage endCursor }
              nodes {
                createdAt
                author { login }
              }
            }
          }
        }
        """
        result = run_query(query, {"org": org, "repo": repo, "cursor": cursor})
        if not result or "repository" not in result:
            print(f"   ⚠️  Failed to fetch PRs for {repo}")
            break
        prs = result["repository"]["pullRequests"]
        for pr in prs["nodes"]:
            author = pr["author"]
            if author and author.get("login"):
                login = author["login"]
                created = pr["createdAt"]
                if login not in user_activity:
                    user_activity[login] = {"prs": 0, "last_pr": created}
                user_activity[login]["prs"] += 1
                user_activity[login]["last_pr"] = later(user_activity[login]["last_pr"], created)
        if not prs["pageInfo"]["hasNextPage"]:
            break
        cursor = prs["pageInfo"]["endCursor"]
        time.sleep(RATE_DELAY)
    return user_activity

def save_to_csv(org, repo_data, all_users):
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"{org}_user_activity_{timestamp}.csv"
    cutoff = datetime.now(timezone.utc) - timedelta(days=THRESHOLD_DAYS)

    with open(filename, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        for repo_name, activity in repo_data.items():
            writer.writerow([f"Repository: {repo_name}"])
            writer.writerow(["Username", "Commits", "Issues", "PRs", "Last Activity", "Status"])
            for user in sorted(all_users):
                data = activity.get(user, {})
                commits = data.get("commits", 0)
                issues = data.get("issues", 0)
                prs = data.get("prs", 0)
                last_commit = data.get("last_commit")
                last_issue = data.get("last_issue")
                last_pr = data.get("last_pr")
                last_activity = later(later(last_commit, last_issue), last_pr)

                if last_activity:
                    dt = datetime.fromisoformat(last_activity.replace("Z", "+00:00"))
                    status = "Active" if dt >= cutoff else "Inactive"
                else:
                    last_activity = "N/A"
                    status = "Inactive"

                writer.writerow([user, commits, issues, prs, last_activity, status])
            writer.writerow([])
    print(f"✅ CSV saved: {filename}")

def main():
    for org in ORG_NAMES:
        print(f"\n🔍 Checking Organization: {org}")
        all_users = get_all_org_members(org)
        repos = get_all_repos(org)
        all_repo_activity = {}

        for repo in repos:
            print(f"\n📦 Repository: {repo}")
            branches = get_branches(org, repo)
            repo_activity = {}

            for branch in branches:
                print(f"   🌿 Branch: {branch}")
                commits = get_commit_activity(org, repo, branch)
                for user, data in commits.items():
                    if user not in repo_activity:
                        repo_activity[user] = {"commits": 0, "issues": 0, "prs": 0,
                                               "last_commit": None, "last_issue": None, "last_pr": None}
                    repo_activity[user]["commits"] += data["commits"]
                    repo_activity[user]["last_commit"] = later(repo_activity[user]["last_commit"], data["last_commit"])

            issues = get_issue_activity(org, repo)
            for user, data in issues.items():
                if user not in repo_activity:
                    repo_activity[user] = {"commits": 0, "issues": 0, "prs": 0,
                                           "last_commit": None, "last_issue": None, "last_pr": None}
                repo_activity[user]["issues"] += data["issues"]
                repo_activity[user]["last_issue"] = later(repo_activity[user]["last_issue"], data["last_issue"])

            prs = get_pr_activity(org, repo)
            for user, data in prs.items():
                if user not in repo_activity:
                    repo_activity[user] = {"commits": 0, "issues": 0, "prs": 0,
                                           "last_commit": None, "last_issue": None, "last_pr": None}
                repo_activity[user]["prs"] += data["prs"]
                repo_activity[user]["last_pr"] = later(repo_activity[user]["last_pr"], data["last_pr"])

            all_repo_activity[repo] = repo_activity

        save_to_csv(org, all_repo_activity, all_users)

if __name__ == "__main__":
    main()
