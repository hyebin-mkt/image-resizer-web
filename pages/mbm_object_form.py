# pages/mbm_object_form.py
import streamlit as st

st.set_page_config(page_title="MBM Object 생성기", page_icon="📄", layout="centered")
st.title("MBM Object 생성기")
st.caption("MBM/Campaign 생성 요청을 접수합니다.")

# HubSpot 설정(하드코딩)
HUBSPOT_REGION = "na1"
PORTAL_ID = "2495902"
FORM_ID = "a9e1a5e8-4c46-461f-b823-13cc4772dc6c"

# f-string 충돌 피하려고 평문 + replace 사용
html = """
<div id="hubspot-form"></div>

<!-- 제출 후 후속 선택 UI (처음엔 숨김) -->
<div id="post-actions" style="display:none; margin-top:24px; padding:16px; border:1px solid #eee; border-radius:12px;">
  <h4 style="margin:0 0 12px;">다음 작업을 선택하세요</h4>
  <label><input type="checkbox" id="make-landing" /> 랜딩페이지 생성</label><br/>
  <label><input type="checkbox" id="make-email" /> 이메일 생성</label>
  <div id="email-count-wrap" style="display:none; margin-top:8px;">
    이메일 발송 횟수: <input id="email-count" type="number" min="1" value="1" style="width:80px;"/>
  </div>
  <button id="do-create" style="margin-top:12px;">생성하기</button>
  <div id="create-result" style="margin-top:8px; display:none;"></div>
</div>

<script>
(function() {
  var s = document.createElement('script');
  s.src = "https://js.hsforms.net/forms/v2.js";
  s.async = true;
  s.onload = function() {
    if (!window.hbspt) return;
    window.hbspt.forms.create({
      region: "__REGION__",
      portalId: "__PORTAL_ID__",
      formId: "__FORM_ID__",
      target: "#hubspot-form",
      inlineMessage: "MBM/Campaign Object가 자동으로 생성되었습니다. 각 오브젝트의 링크를 메일로 보내드릴게요.",
      onFormSubmitted: function() {
        var actions = document.getElementById('post-actions');
        if (actions) actions.style.display = 'block';
      }
    });
  };
  document.body.appendChild(s);

  // 이메일 체크 시 횟수 입력칸 토글
  document.addEventListener('change', function(e){
    if (e.target && e.target.id === 'make-email') {
      var wrap = document.getElementById('email-count-wrap');
      wrap.style.display = e.target.checked ? 'block' : 'none';
    }
  });

  // 생성하기 클릭 (※ 실제 HubSpot 템플릿 복제 연동은 추후)
  document.addEventListener('click', function(e){
    if (e.target && e.target.id === 'do-create') {
      var payload = {
        makeLanding: document.getElementById('make-landing').checked,
        makeEmail: document.getElementById('make-email').checked,
        emailCount: parseInt(document.getElementById('email-count').value || '1', 10)
      };
      console.log('post-submit selections', payload);
      var res = document.getElementById('create-result');
      res.style.display = 'block';
      res.textContent = "요청을 접수했습니다. (API/워크플로우 연동 필요)";
    }
  });
})();
</script>
""".replace("__REGION__", HUBSPOT_REGION)\
   .replace("__PORTAL_ID__", PORTAL_ID)\
   .replace("__FORM_ID__", FORM_ID)

st.components.v1.html(html, height=1200, scrolling=True)
