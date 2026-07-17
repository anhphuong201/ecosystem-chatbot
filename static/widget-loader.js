/**
 * Ecosystem chatbot floating launcher.
 * Include with: <script src="https://ecosystem-chatbot.onrender.com/static/widget-loader.js"></script>
 * Injects a floating chat icon (bottom-right) that opens/closes an iframe
 * pointing back at this same backend's chat.html.
 */
(function () {
  var BACKEND_URL = (document.currentScript && new URL(document.currentScript.src).origin)
    || "https://ecosystem-chatbot.onrender.com";

  var CSS = "\
    .eco-chat-wrapper {\
      position: fixed; bottom: 24px; right: 24px; z-index: 9999;\
      font-family: 'DM Sans', Arial, sans-serif;\
      display: flex; flex-direction: column; align-items: flex-end; gap: 10px;\
    }\
    .eco-chat-window {\
      display: none;\
      width: 500px; height: 580px;\
      max-width: calc(100vw - 32px); max-height: calc(100vh - 120px);\
      border-radius: 16px; overflow: hidden;\
      box-shadow: 0 8px 32px rgba(0,0,0,0.2);\
    }\
    .eco-chat-window.open { display: block; }\
    .eco-chat-window iframe { width: 100%; height: 100%; border: 0; }\
    .eco-toggle-area { position: relative; }\
    .eco-chat-tooltip {\
      position: absolute; bottom: 76px; right: 0;\
      background: #0a4f6e; color: white;\
      padding: 11px 15px; border-radius: 14px 14px 0 14px;\
      font-size: 13.5px; width: 220px; line-height: 1.55;\
      box-shadow: 0 4px 20px rgba(10,79,110,0.35);\
      cursor: pointer; white-space: normal; word-wrap: break-word;\
      opacity: 0; visibility: hidden; transform: translateY(6px);\
      transition: opacity 0.18s ease, transform 0.18s ease, visibility 0.18s ease;\
      pointer-events: none;\
    }\
    .eco-chat-tooltip.visible {\
      opacity: 1 !important; visibility: visible !important;\
      transform: translateY(0) !important; pointer-events: auto !important;\
    }\
    .eco-tooltip-title { font-size: 14px; }\
    .eco-tooltip-hint { margin-top: 5px; font-size: 11.5px; opacity: 0.7; }\
    .eco-chat-toggle {\
      width: 64px; height: 64px; background: #0a4f6e; border-radius: 50%;\
      cursor: pointer; display: flex; align-items: center; justify-content: center;\
      box-shadow: 0 4px 20px rgba(10,79,110,0.5);\
      transition: transform 0.2s, background 0.2s;\
      position: relative;\
    }\
    .eco-online-dot {\
      position: absolute; top: 2px; right: 2px;\
      width: 15px; height: 15px; background: #85be00;\
      border-radius: 50%; border: 2.5px solid white;\
    }\
    @media (max-width: 600px) {\
      .eco-chat-window.open { width: calc(100vw - 24px); height: calc(100vh - 140px); }\
      .eco-chat-wrapper { right: 12px; bottom: 12px; }\
      .eco-chat-tooltip { display: none; }\
    }\
  ";

  var HTML = "\
    <div class=\"eco-chat-window\" id=\"eco-chat-window\">\
      <iframe src=\"" + BACKEND_URL + "\" title=\"Atlantic Innovation Ecosystem Chatbot\"></iframe>\
    </div>\
    <div class=\"eco-toggle-area\" id=\"eco-toggle-area\">\
      <div class=\"eco-chat-tooltip\" id=\"eco-chat-tooltip\">\
        <strong class=\"eco-tooltip-title\">Hi there! 👋</strong><br>\
        Ask me about research &amp; entrepreneurship resources.\
        <div class=\"eco-tooltip-hint\">Click to open →</div>\
      </div>\
      <div class=\"eco-chat-toggle\" id=\"eco-chat-toggle\">\
        <svg class=\"eco-icon-chat\" width=\"28\" height=\"28\" viewBox=\"0 0 24 24\" fill=\"none\">\
          <path d=\"M20 2H4C2.9 2 2 2.9 2 4V22L6 18H20C21.1 18 22 17.1 22 16V4C22 2.9 21.1 2 20 2Z\" fill=\"white\"/>\
          <circle cx=\"8\" cy=\"10\" r=\"1.2\" fill=\"#0a4f6e\"/>\
          <circle cx=\"12\" cy=\"10\" r=\"1.2\" fill=\"#0a4f6e\"/>\
          <circle cx=\"16\" cy=\"10\" r=\"1.2\" fill=\"#0a4f6e\"/>\
        </svg>\
        <svg class=\"eco-icon-close\" width=\"22\" height=\"22\" viewBox=\"0 0 24 24\" fill=\"none\" style=\"display:none;\">\
          <path d=\"M18 6L6 18M6 6l12 12\" stroke=\"white\" stroke-width=\"2.5\" stroke-linecap=\"round\"/>\
        </svg>\
        <div class=\"eco-online-dot\"></div>\
      </div>\
    </div>\
  ";

  function mount() {
    var styleEl = document.createElement("style");
    styleEl.textContent = CSS;
    document.head.appendChild(styleEl);

    var wrapper = document.createElement("div");
    wrapper.className = "eco-chat-wrapper";
    wrapper.innerHTML = HTML;
    document.body.appendChild(wrapper);

    var chatWindow = wrapper.querySelector("#eco-chat-window");
    var toggleArea = wrapper.querySelector("#eco-toggle-area");
    var tooltip    = wrapper.querySelector("#eco-chat-tooltip");
    var toggleBtn  = wrapper.querySelector("#eco-chat-toggle");
    var iconChat   = wrapper.querySelector(".eco-icon-chat");
    var iconClose  = wrapper.querySelector(".eco-icon-close");

    function isOpen() { return chatWindow.classList.contains("open"); }

    function hideTooltip() { tooltip.classList.remove("visible"); }

    function showTooltip() {
      if (!isOpen()) tooltip.classList.add("visible");
    }

    function toggleChat() {
      var opening = !isOpen();
      chatWindow.classList.toggle("open", opening);
      iconChat.style.display  = opening ? "none" : "block";
      iconClose.style.display = opening ? "block" : "none";
      hideTooltip();
    }

    toggleArea.addEventListener("mouseenter", showTooltip);
    toggleArea.addEventListener("mouseleave", hideTooltip);
    toggleBtn.addEventListener("click", toggleChat);
    tooltip.addEventListener("click", toggleChat);
    toggleBtn.addEventListener("mouseover", function () {
      toggleBtn.style.background = "#10879e";
      toggleBtn.style.transform  = "scale(1.08)";
    });
    toggleBtn.addEventListener("mouseout", function () {
      toggleBtn.style.background = "#0a4f6e";
      toggleBtn.style.transform  = "scale(1)";
    });
  }

  if (document.body) {
    mount();
  } else {
    document.addEventListener("DOMContentLoaded", mount);
  }
})();
