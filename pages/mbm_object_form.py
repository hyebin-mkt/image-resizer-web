# pages/mbm-object-form.py
import streamlit as st

# 브라우저 탭 제목/아이콘
st.set_page_config(page_title="MBM Object 생성기", page_icon="📄", layout="centered")

# 본문 타이틀(사이드바 라벨은 파일명 기준이라 따로 표시)
st.title("MBM Object 생성기")
st.caption("MBM/Campaign 생성 요청을 접수합니다.")

# HubSpot Embed (요구사항: 하드코딩)
HUBSPOT_REGION = "na1"
PORTAL_ID = "2495902"
FORM_ID   = "a9e1a5e8-4c46-461f-b823-13cc4772dc6c"

# 최소 스타일(원치 않으면 styles 블록 통째로 지워도 됩니다)
html = f"""
<div id="hubspot-form"></div>

<script>
(function() {{
  var s = document.createElement('script');
  s.src = "https://js.hsforms.net/forms/v2.js";
  s.async = true;
  s.onload = function() {{
    if (!window.hbspt) return;
    window.hbspt.forms.create({{
      region: "{HUBSPOT_REGION}",
      portalId: "{PORTAL_ID}",
      formId: "{FORM_ID}",
      target: "#hubspot-form",
      inlineMessage: "MBM/Campaign Object가 자동으로 생성되었습니다. 각 오브젝트의 링크를 메일로 보내드릴게요."
      // redirectUrl: "https://one-shot-image.streamlit.app/?page=mbm-object-form" // 필요시 사용
    }});
  }};
  document.body.appendChild(s);
}})();
</script>
"""

st.components.v1.html(html, height=900, scrolling=True)

st.divider()


# ====== (선택) 후속 작업 UI 골격 ======
with st.expander("폼 제출 후 선택 옵션 (선택 사항)"):
    make_landing = st.checkbox("랜딩페이지 생성")
    make_email   = st.checkbox("이메일 생성")
    email_count  = 0
    if make_email:
        email_count = st.number_input("이메일 발송 횟수", min_value=1, step=1, value=1)

    # 실제 생성(복제)은 HubSpot API/워크플로우 연동이 필요합니다.
    if st.button("생성하기", type="primary"):
        # TODO: 여기에서 HubSpot Private App Token으로
        # 1) 랜딩페이지 템플릿 복제
        # 2) 마케팅 이메일 템플릿 복제
        # 3) 이름 규칙: "{MBM Object 타이틀}_Landing Page" 등으로 적용
        # 를 호출하세요.
        st.success("요청을 접수했습니다. (템플릿 복제 로직 연동 필요)")
