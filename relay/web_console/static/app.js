/**
 * 需配置：在页面加载前设置 window.__CONSOLE_TOKEN__（或通过 prompt）。
 * API 与 WebSocket 使用同一 token。
 */
(function () {
  const token =
    window.__CONSOLE_TOKEN__ ||
    (typeof localStorage !== "undefined" && localStorage.getItem("console_token")) ||
    prompt("Console Token:") ||
    "";
  if (typeof localStorage !== "undefined" && token) localStorage.setItem("console_token", token);

  const headers = { "X-Console-Token": token, "Content-Type": "application/json" };
  let selectedDevice = null;
  let ws = null;

  const el = (id) => document.getElementById(id);
  const log = (m) => {
    const p = el("log");
    p.textContent = `${new Date().toISOString()} ${m}\n` + p.textContent;
  };

  async function api(path, opts = {}) {
    const r = await fetch(path, { ...opts, headers: { ...headers, ...opts.headers } });
    if (!r.ok) throw new Error(`${path} ${r.status}`);
    return r.json();
  }

  async function refreshDevices() {
    const data = await api("/api/devices");
    const ul = el("device-list");
    ul.innerHTML = "";
    (data.devices || []).forEach((d) => {
      const li = document.createElement("li");
      li.textContent = `${d.device_id} · ${d.model || "?"} · ${d.status || ""}`;
      li.dataset.id = d.device_id;
      if (d.device_id === selectedDevice) li.classList.add("active");
      li.onclick = () => {
        selectedDevice = d.device_id;
        [...ul.children].forEach((c) => c.classList.remove("active"));
        li.classList.add("active");
      };
      ul.appendChild(li);
    });
  }

  async function refreshHistory() {
    const data = await api("/api/history?limit=30");
    el("history").textContent = JSON.stringify(data.history || [], null, 2);
  }

  async function sendCommand(body) {
    const res = await api("/api/command", { method: "POST", body: JSON.stringify(body) });
    log(`command ok: ${JSON.stringify(res.result || {}).slice(0, 200)}`);
    await refreshHistory();
    return res.result;
  }

  function connectWs() {
    const proto = location.protocol === "https:" ? "wss" : "ws";
    ws = new WebSocket(`${proto}://${location.host}/ws/console`);
    ws.onopen = () => {
      ws.send(JSON.stringify({ token }));
      el("conn-pill").textContent = "WS: 已连接";
      el("conn-pill").style.borderColor = "#238636";
    };
    ws.onclose = () => {
      el("conn-pill").textContent = "WS: 断开";
      el("conn-pill").style.borderColor = "#f85149";
      setTimeout(connectWs, 3000);
    };
    ws.onmessage = (ev) => {
      try {
        const msg = JSON.parse(ev.data);
        if (msg.type === "device_status" || msg.type === "devices_updated") refreshDevices();
      } catch (_) {}
    };
  }

  el("btn-shot").onclick = async () => {
    if (!selectedDevice) return alert("请选择设备");
    const fmt = el("shot-format").value || "jpeg";
    const q = parseInt(el("shot-quality").value, 10) || 72;
    const maxw = parseInt(el("shot-maxw").value, 10);
    const maxWParam = Number.isFinite(maxw) && maxw >= 0 ? maxw : 0;
    const qs = new URLSearchParams({
      format: fmt,
      quality: String(q),
      max_width: String(maxWParam),
    });
    const r = await api(`/api/screenshot/${encodeURIComponent(selectedDevice)}?${qs.toString()}`);
    const data = (r.result && r.result.data) || {};
    const b64 = data.screenshot_base64 || "";
    const mime = data.mime_type || "image/png";
    const wrap = el("screen-wrap");
    if (b64) {
      wrap.innerHTML = "";
      const img = document.createElement("img");
      img.src = `data:${mime};base64,` + b64;
      img.onclick = (e) => {
        const rect = img.getBoundingClientRect();
        const x = Math.round(((e.clientX - rect.left) / rect.width) * img.naturalWidth);
        const y = Math.round(((e.clientY - rect.top) / rect.height) * img.naturalHeight);
        sendCommand({ device_id: selectedDevice, action: "tap", params: { x, y } });
      };
      wrap.appendChild(img);
    }
  };

  el("btn-home").onclick = () =>
    selectedDevice && sendCommand({ device_id: selectedDevice, action: "key_event", params: { keycode: 3 } });
  el("btn-back").onclick = () =>
    selectedDevice && sendCommand({ device_id: selectedDevice, action: "key_event", params: { keycode: 4 } });

  el("btn-send-text").onclick = () => {
    const text = el("inp-text").value;
    if (selectedDevice && text) sendCommand({ device_id: selectedDevice, action: "input_text", params: { text } });
  };

  el("btn-launch").onclick = () => {
    const pkg = el("inp-pkg").value;
    if (selectedDevice && pkg) sendCommand({ device_id: selectedDevice, action: "launch_app", params: { package: pkg } });
  };

  el("btn-dag").onclick = () => {
    const dag = el("sel-dag").value;
    if (!selectedDevice) return;
    api("/api/dag/run", {
      method: "POST",
      body: JSON.stringify({ device_id: selectedDevice, dag_name: dag }),
    })
      .then((r) => log("dag: " + JSON.stringify(r).slice(0, 300)))
      .then(() => refreshHistory());
  };

  refreshDevices().catch((e) => log(String(e)));
  refreshHistory().catch(() => {});
  connectWs();
  setInterval(() => refreshDevices().catch(() => {}), 8000);
})();
