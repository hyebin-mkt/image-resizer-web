# pages/Feedback.py
import datetime
import requests
import streamlit as st

st.set_page_config(page_title="Feedback", page_icon="💬", layout="centered")
st.title("💬 Feedback")
st.caption("커뮤니티 형식의 댓글/대댓글 공간입니다. (GitHub Issues 기반)")

# ----- sidebar identical style -----
def sidebar_quick_link(label: str, url: str):
    st.sidebar.markdown(
        f'''
<a href="{url}" target="_blank" style="text-decoration:none;">
  <div style="
      display:flex; align-items:center; justify-content:space-between;
      padding:12px 14px; margin:6px 0;
      border:1px solid #e5e7eb; border-radius:12px;
      background:#fff; transition:all .15s ease;">
    <span style="font-weight:600; color:#111827;">{label}</span>
    <span style="font-size:14px; color:#6b7280;">↗</span>
  </div>
</a>
''',
        unsafe_allow_html=True
    )

with st.sidebar:
    st.subheader("바로가기")
    sidebar_quick_link("Hubspot File 바로가기", "https://app.hubspot.com/files/2495902/")
    sidebar_quick_link("Hubspot Website 바로가기", "https://app.hubspot.com/page-ui/2495902/management/pages/site/all")
    sidebar_quick_link("MBM 가이드북", "https://www.canva.com/design/DAGtMIVovm8/eXz5TOekAVik-uynq1JZ1Q/view?utm_content=DAGtMIVovm8&utm_campaign=designshare&utm_medium=link2&utm_source=uniquelinks&utlId=h9b120a74ea")
    st.markdown("""
    <style>
    [data-testid="stSidebar"] .sidebar-copyright{
      position: sticky; bottom: 18px; margin-top: 24px;
    }
    </style>
    """, unsafe_allow_html=True)
    st.sidebar.markdown(
        '<div class="sidebar-copyright" style="color:#6b7280; font-size:12px;">'
        '© Chacha · <a href="mailto:chb0218@midasit.com" style="color:#6b7280; text-decoration:none;">chb0218@midasit.com</a>'
        '</div>',
        unsafe_allow_html=True
    )

# ----- GitHub helpers -----
def _gh_headers(token: str):
    return {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "streamlit-feedback-page",
    }

def create_issue(repo_full: str, token: str, title: str, body: str, labels=None):
    url = f"https://api.github.com/repos/{repo_full}/issues"
    payload = {"title": title, "body": body}
    if labels: payload["labels"] = labels
    return requests.post(url, headers=_gh_headers(token), json=payload)

def list_issues(repo_full: str, token: str, state="open", per_page=20):
    url = f"https://api.github.com/repos/{repo_full}/issues"
    r = requests.get(url, headers=_gh_headers(token), params={"state": state, "per_page": per_page})
    return r.json() if r.status_code == 200 else []

def add_issue_comment(repo_full: str, token: str, number: int, body: str):
    url = f"https://api.github.com/repos/{repo_full}/issues/{number}/comments"
    return requests.post(url, headers=_gh_headers(token), json={"body": body})

def list_issue_comments(repo_full: str, token: str, number: int):
    url = f"https://api.github.com/repos/{repo_full}/issues/{number}/comments"
    r = requests.get(url, headers=_gh_headers(token))
    return r.json() if r.status_code == 200 else []

# ----- secrets -----
gh_token = st.secrets.get("GH_TOKEN")
gh_repo  = st.secrets.get("GH_REPO")  # 예: "owner/repo"

if not gh_token or not gh_repo:
    st.info("관리자 안내: Secrets에 `GH_TOKEN`, `GH_REPO`를 설정하면 댓글/대댓글이 저장됩니다.")
    st.stop()

# ===== 새 댓글(=새 이슈) =====
st.markdown("### ✍️ 새 댓글 남기기")
with st.form("fb_new_issue", border=True):
    email = st.text_input("이메일(표시용)")
    content = st.text_area("댓글", height=120, placeholder="내용을 작성하세요.")
    ok = st.form_submit_button("게시", type="primary")
    if ok:
        if not content.strip():
            st.error("댓글 내용을 입력해주세요.")
        else:
            title = f"[커뮤니티] {content.strip()[:40]}"
            now = datetime.datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")
            body = f"**작성자:** {email or '-'}\n**시간(UTC):** {now}\n\n{content}"
            res = create_issue(gh_repo, gh_token, title, body, labels=["community"])
            if 200 <= res.status_code < 300:
                st.success("등록되었습니다.")
                st.experimental_rerun()
            else:
                st.error(f"실패: {res.status_code} - {res.text}")

st.divider()

# ===== 스레드 목록 + 대댓글 =====
st.markdown("### 🧵 최근 댓글 스레드")
issues = list_issues(gh_repo, gh_token, state="all", per_page=20)
if not issues or isinstance(issues, dict) and issues.get("message"):
    st.caption("표시할 항목이 없습니다.")
else:
    for it in issues:
        num = it.get("number")
        title = it.get("title") or "(제목 없음)"
        user  = it.get("user", {}).get("login", "")
        ts    = (it.get("created_at") or "")[:16].replace("T"," ")
        head  = f"#{num} · {title}  —  {user} · {ts}"

        with st.expander(head, expanded=False):
            body = it.get("body") or ""
            st.markdown(body)

            cmts = list_issue_comments(gh_repo, gh_token, num)
            if cmts:
                st.markdown("---")
                st.markdown(f"**대댓글 {len(cmts)}개**")
                for c in cmts:
                    cuser = c.get("user", {}).get("login", "")
                    ctime = (c.get("created_at") or "")[:16].replace("T"," ")
                    cbody = c.get("body") or ""
                    with st.expander(f"↳ {cuser} — {ctime}", expanded=False):
                        st.markdown(cbody)

            st.markdown("---")
            with st.form(f"reply_{num}"):
                reply = st.text_area("대댓글", key=f"reply_txt_{num}", height=100, placeholder="여기에 대댓글을 입력하세요")
                posted = st.form_submit_button("대댓글 게시")
                if posted:
                    res = add_issue_comment(gh_repo, gh_token, num, reply or "")
                    if 200 <= res.status_code < 300:
                        st.success("등록되었습니다.")
                        st.experimental_rerun()
                    else:
                        st.error(f"실패: {res.status_code} - {res.text}")
