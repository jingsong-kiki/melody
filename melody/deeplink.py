import os
from urllib.parse import quote


def build(client, public_id, repo_name, code_root):
    prompt = f"处理 melody 事项卡 {public_id}"
    directory = _directory(repo_name, code_root)
    if client == "cursor":
        text = prompt
        if repo_name:
            text = f"{prompt}。仓库 {repo_name}。请确认当前工作区。"
        return "cursor://anysphere.cursor-deeplink/prompt?text=" + quote(text)
    if client == "codex":
        url = "codex://new?prompt=" + quote(prompt)
        if directory:
            url += "&path=" + quote(directory)
        return url
    url = "claude-cli://open?q=" + quote(prompt)
    if directory:
        url += "&cwd=" + quote(directory)
    return url


def _directory(repo_name, code_root):
    if not repo_name or not code_root:
        return ""
    candidate = os.path.join(code_root, repo_name)
    if os.path.isdir(candidate):
        return candidate
    return ""
