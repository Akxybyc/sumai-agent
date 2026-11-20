const S = {
  logs: [],
  drafts: [],
  tasks: [],
  stats: { pending: 0, approved: 0, submitted: 0, on_sale: 0, total: 0 },
  settings: null,
  providers: [],
  usage: { calls: 0, tokens: 0, est_cost: 0 },
  selected: new Set(),
  picked: new Set(),
  reviewPage: 1,
  reviewSize: 5,
  pollTimer: null,
  view: "chat",
};

const $ = (sel) => document.querySelector(sel);
const $$ = (sel) => Array.from(document.querySelectorAll(sel));

/* ---------------- 基础 ---------------- */
function esc(str = "") {
  return String(str).replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
}
function md(str = "") {
  return esc(str).replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>").replace(/\n/g, "<br>");
}
function gradient(hue, light = 90) {
  return `background: linear-gradient(145deg, hsl(${hue} 78% ${light + 4}%), hsl(${hue} 68% ${light - 6}%));`;
}
function toast(msg) {
  const t = $("#toast");
  t.textContent = msg;
  t.classList.add("show");
  clearTimeout(t._timer);
  t._timer = setTimeout(() => t.classList.remove("show"), 2200);
}

async function api(path, opts = {}) {
  const res = await fetch(path, {
    headers: { "Content-Type": "application/json" },
    ...opts,
    body: opts.body ? JSON.stringify(opts.body) : undefined,
  });
  if (!res.ok) {
    const text = await res.text();
    throw new Error(text || res.statusText);
  }
  return res.json();
}

async function loadProviders() {
  try {
    const r = await api("/api/llm/providers");
    S.providers = r.providers || [];
    S.llmTasks = r.tasks || [];
    const opts = S.providers.map((p) => `<option value="${p.id}">${esc(p.name)}</option>`).join("");
    $("#setProvider").innerHTML = opts;
    $("#setFallback").innerHTML = opts;
  } catch (e) {
    console.warn("providers load failed", e);
  }
}

function providerById(id) {
  return S.providers.find((p) => p.id === id) || {};
}

/* ---------------- 视图切换 ---------------- */
const VIEW_META = {
  chat: ["对话工作台", "用一句话完成选品、生成内容与全托管提报"],
  review: ["审核台", "人工把关：标题、供货价、库存、SKU 编码确认后才提报"],
  tasks: ["任务看板", "选品、生成、提报的执行进度与结果"],
  settings: ["设置", "店铺、模型算力、数据源与驱动"],
};

function switchView(name) {
  S.view = name;
  $$(".nav-item").forEach((b) => b.classList.toggle("active", b.dataset.view === name));
  $$(".view").forEach((v) => v.classList.toggle("active", v.id === `view-${name}`));
  $("#pageTitle").textContent = VIEW_META[name][0];
  $("#pageSub").textContent = VIEW_META[name][1];
  if (name === "review") renderReview();
  if (name === "tasks") renderTasks();
}
window.switchView = switchView;

/* ---------------- 对话 ---------------- */
function welcome() {
  return {
    role: "agent",
    time: "",
    text:
      "早上好，我是你的上品助手。\n\n" +
      "现在可以帮你：**1688 选品 → 生成英文提报内容 → 全托管提报**。\n" +
      "所有提报动作都会先经过你的审核，不会擅自提交。\n\n" +
      "说一句「找厨房类目最近卖得好的新品」试试？",
    type: "guide",
  };
}

function renderMessage(log) {
  const isUser = log.role === "user";
  const wrap = document.createElement("div");
  wrap.className = `msg ${isUser ? "user" : "agent"}${log.type === "err" ? " err" : ""}`;
  wrap.innerHTML = `
    <div class="m-avatar">${isUser ? "你" : "A"}</div>
    <div class="m-body">
      <div class="m-meta">${isUser ? "你" : "上品助手"}${log.time ? ` · ${log.time}` : ""}</div>
      <div class="m-text">${md(log.text)}</div>
    </div>`;
  $("#chatList").appendChild(wrap);

  if (log.type === "candidates" && log.items) renderCandidates(log.items);
  if (log.type === "real" && log.items) {
    renderCandidates(log.items, true);
    S.selected.clear();
    const wrapEl = $("#chatList").lastElementChild;
    const info = wrapEl && wrapEl.querySelector(".sel-info");
    if (info) info.innerHTML = `已生成 <b>${(log.draft_ids || []).length}</b> 个草稿 · 等待你在审核台确认`;
    const btn = wrapEl && wrapEl.querySelector('[data-act="confirm"]');
    if (btn) {
      const clone = btn.cloneNode(true);
      clone.textContent = `去审核台确认（${(log.draft_ids || []).length} 个）`;
      clone.disabled = false;
      clone.addEventListener("click", () => switchView("review"));
      btn.replaceWith(clone);
    }
    refreshData();
  }
  if (log.type === "auto" && log.items) {
    S.selected = new Set(log.auto_ids || []);
    renderCandidates(log.items, true);
    if (log.job_id) attachJobCard(log.job_id, "生成提报内容");
  }
  if (log.type === "candidates" || log.type === "auto" || log.type === "real") {
    const sc = $("#chatScroll");
    const top = wrap.getBoundingClientRect().top - sc.getBoundingClientRect().top + sc.scrollTop;
    sc.scrollTop = Math.max(0, top - 16);
  } else {
    scrollChat();
  }
}

function renderCandidates(items, auto = false) {
  const live = items.some((i) => i.source === "rpa1688");
  const wrap = document.createElement("div");
  wrap.className = "cand-wrap";
  wrap.innerHTML = `
    <div class="cand-toolbar">
      <div class="cand-count"><b>${items.length}</b> 个候选 · 数据源 ${live ? "1688 实时采集" : "1688 开放平台"}</div>
      <button class="link-btn" data-act="toggle-all">全选</button>
    </div>
    <div class="pgrid">
      ${items
        .map(
          (it) => `
        <div class="pcard" data-id="${it.id}">
          <div class="pimg" style="${gradient(it.hue)}">
            <span class="pcheck">✓</span>
            <span class="psrc">1688</span>
            ${it.image ? `<img src="${esc(it.image)}" referrerpolicy="no-referrer" loading="lazy" alt="" />` : `<span>${it.icon || "📦"}</span>`}
          </div>
          <div class="pbody">
            <div class="ptitle">${esc(it.title)}</div>
            ${
              auto && it.score
                ? `<div class="pscore">策略分 ${it.score}</div><div class="preason">${esc(it.reason || "")}</div>`
                : ""
            }
            <div class="pmeta">
              <span class="pprice">¥${Number(it.price_cny).toFixed(2)}</span>
              <span class="sep"></span>
              <span>30天 ${Number(it.sales_30d || 0).toLocaleString()}</span>
              <span class="sep"></span>
              <span>${it.repurchase_rate ? `回头率 ${it.repurchase_rate}%` : `采集 ${it.collectors || 0}`}</span>
            </div>
          </div>
        </div>`
        )
        .join("")}
    </div>
    <div class="cand-foot">
      <div class="sel-info">已选 <b data-role="count">0</b> 个<span data-role="eta-wrap" hidden> · 预计生成 <b data-role="eta">0</b> 分钟</span></div>
      <button class="btn primary" data-act="confirm" disabled>${auto ? "按当前勾选重新生成" : "确认选品，生成提报内容"}</button>
    </div>`;
  $("#chatList").appendChild(wrap);

  const update = () => {
    const n = S.selected.size;
    wrap.querySelector('[data-role="count"]').textContent = n;
    wrap.querySelector('[data-role="eta"]').textContent = Math.max(1, Math.round(n * 0.12));
    wrap.querySelector('[data-role="eta-wrap"]').hidden = n === 0;
    wrap.querySelector('[data-act="confirm"]').disabled = n === 0;
    wrap.querySelectorAll(".pcard").forEach((c) => c.classList.toggle("selected", S.selected.has(c.dataset.id)));
    wrap.querySelector('[data-act="toggle-all"]').textContent =
      n === items.length ? "取消全选" : "全选";
  };

  wrap.querySelectorAll(".pcard").forEach((card) => {
    card.addEventListener("click", () => {
      const id = card.dataset.id;
      S.selected.has(id) ? S.selected.delete(id) : S.selected.add(id);
      update();
    });
  });
  wrap.querySelector('[data-act="toggle-all"]').addEventListener("click", () => {
    if (S.selected.size === items.length) S.selected.clear();
    else items.forEach((i) => S.selected.add(i.id));
    update();
  });
  wrap.querySelector('[data-act="confirm"]').addEventListener("click", () => generate(wrap));
  update();
}

function attachJobCard(jobId, title) {
  const jobBox = document.createElement("div");
  jobBox.className = "job-card";
  jobBox.innerHTML = `
    <div class="job-head"><span>${esc(title)}</span><span class="pct">0%</span></div>
    <div class="job-step">正在创建任务…</div>
    <div class="bar"><i></i></div>`;
  $("#chatList").appendChild(jobBox);
  scrollChat();
  pollJob(
    jobId,
    jobBox,
    (job) => {
      jobBox.querySelector(".pct").textContent = `${job.progress || 0}%`;
      jobBox.querySelector(".job-step").textContent = job.step || "处理中…";
      jobBox.querySelector(".bar > i").style.width = `${job.progress || 0}%`;
    },
    (job) => {
      jobBox.querySelector(".job-head span:first-child").textContent = "生成完成";
      jobBox.querySelector(".job-step").textContent = job.step || "已完成";
      const act = document.createElement("div");
      act.className = "job-actions";
      act.innerHTML = `<button class="btn primary small">去审核台确认（${job.total} 个）</button>`;
      act.querySelector("button").addEventListener("click", () => switchView("review"));
      jobBox.appendChild(act);
      refreshData();
      toast("已自动完成选品与内容生成，等待你审核");
    }
  );
}

async function generate(wrap) {
  const ids = Array.from(S.selected);
  if (!ids.length) return;
  const btn = wrap.querySelector('[data-act="confirm"]');
  btn.disabled = true;
  btn.textContent = "正在生成…";

  const jobBox = document.createElement("div");
  jobBox.className = "job-card";
  jobBox.innerHTML = `
    <div class="job-head"><span>生成提报内容</span><span class="pct">0%</span></div>
    <div class="job-step">正在创建任务…</div>
    <div class="bar"><i></i></div>`;
  $("#chatList").appendChild(jobBox);
  scrollChat();

  try {
    const { job_id } = await api("/api/generate", { method: "POST", body: { ids } });
    S.selected.clear();
    pollJob(job_id, jobBox, (job) => {
      jobBox.querySelector(".pct").textContent = `${job.progress || 0}%`;
      jobBox.querySelector(".job-step").textContent = job.step || "处理中…";
      jobBox.querySelector(".bar > i").style.width = `${job.progress || 0}%`;
    }, (job) => {
      jobBox.querySelector(".job-head span:first-child").textContent = "生成完成";
      jobBox.querySelector(".job-step").textContent = job.step || "已完成";
      const act = document.createElement("div");
      act.className = "job-actions";
      act.innerHTML = `<button class="btn primary small">去审核台确认（${job.total} 个）</button>`;
      act.querySelector("button").addEventListener("click", () => switchView("review"));
      jobBox.appendChild(act);
      refreshData();
      toast("草稿已生成，等待人工审核");
    });
  } catch (e) {
    btn.disabled = false;
    btn.textContent = "确认选品，生成提报内容";
    jobBox.querySelector(".job-step").textContent = `生成失败：${e.message}`;
  }
}

function pollJob(jobId, box, onTick, onDone) {
  clearInterval(S.pollTimer);
  const tick = async () => {
    try {
      const job = await api(`/api/job/${jobId}`);
      onTick(job);
      if (job.status === "done") {
        clearInterval(S.pollTimer);
        onDone(job);
      }
    } catch (e) {
      clearInterval(S.pollTimer);
      box.querySelector(".job-step").textContent = `任务中断：${e.message}`;
    }
  };
  tick();
  S.pollTimer = setInterval(tick, 650);
}

function scrollChat() {
  const el = $("#chatScroll");
  el.scrollTop = el.scrollHeight;
}

function showTyping() {
  hideTyping();
  const box = $("#chatList") || document.querySelector(".messages");
  if (!box) return;
  const el = document.createElement("div");
  el.className = "msg agent";
  el.id = "typingMsg";
  el.innerHTML = '<div class="bubble"><span class="typing"><i></i><i></i><i></i></span></div>';
  box.appendChild(el);
  box.scrollTop = box.scrollHeight;
}

function hideTyping() {
  const el = document.getElementById("typingMsg");
  if (el) el.remove();
}

async function send(text) {
  const value = (text || $("#input").value).trim();
  if (!value) return;
  $("#input").value = "";
  autoGrow();
  renderMessage({ role: "user", text: value, time: nowTime() });
  const btn = $("#sendBtn");
  if (btn) { btn.disabled = true; btn.textContent = "处理中"; }
  showTyping();
  try {
    const res = await api("/api/chat", { method: "POST", body: { text: value } });
    hideTyping();
    renderMessage(res.message);
    if (res.trace && res.trace.length) {
      const failed = res.trace.filter((t) => t.result_ok === false);
      if (failed.length) {
        renderMessage({
          role: "agent",
          text: "工具调用未成功：\n" + failed.map((t) => `· ${t.tool}：${t.message || "无返回"} `).join("\n"),
          time: nowTime(),
          type: "err",
        });
      }
    }
  } catch (e) {
    hideTyping();
    renderMessage({
      role: "agent",
      text: `请求失败：${e.message}\n（如果是模型报错，检查设置里的 Base URL / 模型名 / Key）`,
      time: nowTime(),
      type: "err",
    });
  } finally {
    if (btn) { btn.disabled = false; btn.textContent = "发送"; }
  }
}

function nowTime() {
  const d = new Date();
  return `${String(d.getHours()).padStart(2, "0")}:${String(d.getMinutes()).padStart(2, "0")}`;
}

/* ---------------- 审核台 ---------------- */
function renderReview() {
  const list = $("#reviewList");
  $("#statPending").textContent = S.stats.pending;
  $("#statApproved").textContent = S.stats.approved;
  $("#statSubmitted").textContent = S.stats.submitted;
  $("#statOnSale").textContent = S.stats.on_sale;

  if (!S.drafts.length) {
    list.innerHTML = `
      <div class="empty">
        <div class="empty-icon">🗂️</div>
        <h3>还没有商品草稿</h3>
        <p>去对话工作台说一句「找 XX 类目新品」，我生成草稿后会出现在这里。</p>
        <button class="btn primary" onclick="switchView('chat')">去选品</button>
      </div>`;
    return;
  }

  const order = { pending: 0, approved: 1, submitted: 2, on_sale: 3 };
  const all = [...S.drafts].sort((a, b) => order[a.status] - order[b.status]);
  const size = S.reviewSize || 5;
  const pages = Math.max(1, Math.ceil(all.length / size));
  S.reviewPage = Math.min(Math.max(1, S.reviewPage || 1), pages);
  const drafts = all.slice((S.reviewPage - 1) * size, S.reviewPage * size);
  const label = { pending: "待审核", approved: "已确认", submitted: "审核中", on_sale: "销售中" };

  list.innerHTML = drafts
    .map(
      (d) => `
    <div class="dcard${S.picked && S.picked.has(d.id) ? " picked" : ""}" data-id="${d.id}">
      <label class="dpick" title="选择"><input type="checkbox" data-pick="${d.id}" ${S.picked && S.picked.has(d.id) ? "checked" : ""} /></label>
      <div class="dthumb" style="${gradient(d.hue)}">
        ${
          d.images && d.images.length
            ? `<img src="${esc(d.images[0])}" alt="" loading="lazy" referrerpolicy="no-referrer" onerror="this.style.display='none'" />`
            : `<span>${d.icon}</span>`
        }
        <em>1688</em>
      </div>
      <div class="dmain">
        <div class="dtop">
          <span class="dstatus ${d.status}">${label[d.status]}</span>
          <span class="code">${esc(d.source_id)} · ${esc(d.category_en.split(">").pop().trim())}</span>
          ${d.ms_detail_id ? `<span class="ms-tag" title="妙手公共采集箱">已入箱 #${d.ms_detail_id}</span>` : ""}
        </div>
        <input class="dtitle" data-field="title_en" value="${esc(d.title_en)}" ${d.status !== "pending" && d.status !== "approved" ? "disabled" : ""} />
        <div class="dtitle-cn">${esc(d.title_cn)}</div>
        <div class="dsrc">
          ${
            d.source_url
              ? `<a href="${esc(d.source_url)}" target="_blank" rel="noreferrer">1688 原链接 ↗</a>`
              : `<span>无来源链接</span>`
          }
          <span>· ${esc(d.source_id || "-")}</span>
          ${d.images && d.images.length > 1 ? `<span>· ${d.images.length} 张图</span>` : ""}
        </div>
        ${
          d.qualification && d.qualification.required
            ? `<div class="qual-alert">⚠ 需资质：${d.qualification.items
                .map((i) => esc(i.name))
                .join("、")} — ${
                d.qual_status === "approved"
                  ? `已登记（证书 ${esc((d.qual_cert && d.qual_cert.cert_no) || "-")}，${esc((d.qual_cert && d.qual_cert.expire) || "无有效期")}）`
                  : "未登记资质，已拦截提报与推送"
              }</div>`
            : ""
        }
        <div class="dfields">
          <label class="dfield"><span>供货价 CNY${d.need_manual_price ? ' <b class="warn-chip">待客户定价</b>' : ""}</span><input type="number" step="0.01" data-field="supply_price" value="${d.supply_price || ""}" placeholder="${d.need_manual_price ? "成本低于10元，请输入你定的价" : ""}" ${d.status !== "pending" && d.status !== "approved" ? "disabled" : ""} /></label>
          ${d.price_rule ? `<div class="price-rule">${esc(d.price_rule)}</div>` : ""}
          <label class="dfield"><span>库存</span><input type="number" data-field="stock" value="${d.stock}" ${d.status !== "pending" && d.status !== "approved" ? "disabled" : ""} /></label>
          <label class="dfield"><span>重量 g</span><input type="number" data-field="weight_g" value="${d.weight_g}" ${d.status !== "pending" && d.status !== "approved" ? "disabled" : ""} /></label>
          <label class="dfield"><span>SKU 编码</span><input data-field="sku_code" value="${esc(d.sku_code)}" ${d.status !== "pending" && d.status !== "approved" ? "disabled" : ""} /></label>
        </div>
        <div class="dattrs">
          <span class="attr">成本 ¥${d.cost_cny.toFixed(2)}</span>
          <span class="attr">${esc(d.warehouse)}</span>
          <span class="attr">备货 ${d.lead_days} 天</span>
          ${Object.entries(d.attrs).slice(0, 3).map(([k, v]) => `<span class="attr">${esc(k)}: ${esc(v)}</span>`).join("")}
          ${d.product_id ? `<span class="attr" style="color:#067647;border-color:#d8f3e7;background:#f2fbf7">商品ID ${d.product_id}</span>` : ""}
        </div>
      </div>
      <div class="dside">
        ${d.source_url ? `<a class="btn ghost small" href="${esc(d.source_url)}" target="_blank" rel="noreferrer" style="text-align:center">原商品 ↗</a>` : ""}
        <button class="btn ghost small" data-act="del" title="删除">删除</button>
        ${
          d.qualification && d.qualification.required && d.qual_status !== "approved"
            ? `<button class="btn ghost small" data-act="qual">登记资质</button><button class="btn ghost small" data-act="skip">稍后处理</button><button class="btn ghost small" data-act="view">查看方案</button>`
            : d.status === "pending"
            ? `<button class="btn primary small" data-act="approve">确认</button><button class="btn ghost small" data-act="skip">稍后处理</button><button class="btn ghost small" data-act="view">查看方案</button>`
            : d.status === "approved"
            ? `<button class="btn primary small" data-act="publish">立即提报</button><button class="btn ghost small" data-act="back">退回修改</button><button class="btn ghost small" data-act="view">查看方案</button>`
            : `<button class="btn ghost small" data-act="view">查看方案</button><span class="tag ${d.status === "submitted" ? "blue" : "green"}" style="text-align:center">${d.status === "submitted" ? "平台审核中" : "已上架销售"}</span>`
        }
      </div>
    </div>`
    )
    .join("");

  list.insertAdjacentHTML(
    "beforeend",
    `<div class="pager">
      <span class="pager-info">第 ${S.reviewPage}/${pages} 页 · 共 ${all.length} 条</span>
      <div class="pager-btns">
        <button class="btn ghost small" data-page="prev" ${S.reviewPage <= 1 ? "disabled" : ""}>上一页</button>
        <button class="btn ghost small" data-page="next" ${S.reviewPage >= pages ? "disabled" : ""}>下一页</button>
        <select class="pager-size">
          ${[5, 10, 20].map((n) => `<option value="${n}" ${n === size ? "selected" : ""}>${n} 条/页</option>`).join("")}
        </select>
      </div>
    </div>`
  );

  list.querySelectorAll("[data-page]").forEach((b) =>
    b.addEventListener("click", () => {
      S.reviewPage += b.dataset.page === "next" ? 1 : -1;
      renderReview();
    })
  );
  const sel = list.querySelector(".pager-size");
  if (sel)
    sel.addEventListener("change", () => {
      S.reviewSize = Number(sel.value);
      S.reviewPage = 1;
      renderReview();
    });

  list.querySelectorAll("[data-pick]").forEach((cb) =>
    cb.addEventListener("change", () => {
      if (!S.picked) S.picked = new Set();
      if (cb.checked) S.picked.add(cb.dataset.pick);
      else S.picked.delete(cb.dataset.pick);
      const card = cb.closest(".dcard");
      if (card) card.classList.toggle("picked", cb.checked);
      syncSelBtns();
    })
  );

  renderGuide();

  list.querySelectorAll(".dcard").forEach((card) => {
    const id = card.dataset.id;
    card.querySelectorAll("input[data-field]").forEach((input) => {
      input.addEventListener("change", () => patchDraft(id, input.dataset.field, input.value));
    });
    card.querySelectorAll("[data-act]").forEach((btn) => {
      btn.addEventListener("click", () => draftAction(id, btn.dataset.act));
    });
  });
}

function patchDraft(id, field, value) {
  const payload = {};
  payload[field] = field === "supply_price" ? parseFloat(value) : ["weight_g", "stock"].includes(field) ? parseInt(value, 10) : value;
  api(`/api/drafts/${id}`, { method: "PATCH", body: payload })
    .then((d) => {
      const idx = S.drafts.findIndex((x) => x.id === d.id);
      if (idx >= 0) S.drafts[idx] = d;
      toast("已保存");
    })
    .catch((e) => toast(`保存失败：${e.message}`));
}

async function draftAction(id, act) {
  if (act === "view") {
    const d = S.drafts.find((x) => x.id === id);
    if (d) openDraftModal(d);
    return;
  }
  if (act === "del") {
    const d = S.drafts.find((x) => x.id === id);
    if (!confirm(`删除「${d ? d.title_cn.slice(0, 20) : id}」这个草稿？`)) return;
    try {
      await api(`/api/drafts/${id}`, { method: "DELETE" });
      await refreshData();
      renderReview();
      toast("已删除");
    } catch (e) {
      toast(`删除失败：${e.message}`);
    }
    return;
  }

  if (act === "qual") {
    const d = S.drafts.find((x) => x.id === id);
    const names = (d.qualification.items || []).map((i) => i.name).join("、");
    const cert = window.prompt(`该商品需资质：${names}\n\n请输入证书/报告编号（取消则放弃）：`);
    if (!cert) return;
    const expire = window.prompt("有效期（YYYY-MM-DD，留空表示长期有效）：", "") || "";
    await api(`/api/drafts/${id}/qualification`, {
      method: "POST",
      body: { status: "approved", cert_no: cert, expire, operator: "运营" },
    });
    await refreshData();
    renderReview();
    toast("资质已登记，可确认提报");
    return;
  }

  if (act === "approve") {
    const d = S.drafts.find((x) => x.id === id);
    if (d && d.qualification && d.qualification.required && d.qual_status !== "approved") {
      toast("需先登记资质");
      return;
    }
    const res = await api("/api/drafts/approve", { method: "POST", body: { ids: [id] } });
    await refreshData();
    renderReview();
    toast(res.blocked && res.blocked.length ? "需资质未登记，已拦截" : "已确认，可提报");
  } else if (act === "skip") {
    toast("已标记稍后处理");
  } else if (act === "back") {
    const d = S.drafts.find((x) => x.id === id);
    if (d) d.status = "pending";
    toast("已退回待审核");
    renderReview();
  } else if (act === "publish") {
    const { job_id, blocked } = await api("/api/publish", { method: "POST", body: { ids: [id] } });
    toast(blocked && blocked.length ? "已提报，需资质的已拦截" : "已开始提报");
    watchPublish(job_id);
  }
}

async function watchPublish(jobId) {
  clearInterval(S.pollTimer);
  S.pollTimer = setInterval(async () => {
    try {
      const job = await api(`/api/job/${jobId}`);
      if (job.status === "done") {
        clearInterval(S.pollTimer);
        await refreshData();
        renderReview();
        toast(job.step || "提报完成");
      }
    } catch (e) {
      clearInterval(S.pollTimer);
      toast(`提报中断：${e.message}`);
    }
  }, 700);
}

/* ---------------- 任务看板 ---------------- */
function renderTasks() {
  const list = $("#taskList");
  if (!S.tasks.length) {
    list.innerHTML = `
      <div class="empty">
        <div class="empty-icon">📋</div>
        <h3>暂无任务</h3>
        <p>生成草稿、提报商品时会自动创建任务，可在这里看进度和失败原因。</p>
      </div>`;
    return;
  }
  const statusMap = {
    running: ['进行中', 'orange'],
    done: ['已完成', 'green'],
    failed: ['失败', 'red'],
    waiting_human: ['等待人工', 'blue'],
  };
  list.innerHTML = [...S.tasks]
    .reverse()
    .map((t) => {
      const [txt, color] = statusMap[t.status] || ["未知", "gray"];
      return `
      <div class="tcard">
        <div class="trow">
          <div>
            <div class="tname">${esc(t.name)} <span class="tag ${color}">${txt}</span></div>
            <div class="tmeta">${esc(t.created_at)} · ${t.kind === "generate" ? "内容生成" : "提报表单"} · 共 ${t.total} 个</div>
          </div>
          <div class="tmeta">成功 ${t.done_count} / 失败 ${t.failed_count}</div>
        </div>
        <div class="tstep">${esc(t.step)}</div>
        <div class="bar"><i style="width:${t.progress}%"></i></div>
        ${t.detail && t.detail.length ? `<div class="tdetail">${t.detail.map((d) => `<span class="titem ok">${esc((d.title || "").slice(0, 34))}${d.pid ? " · " + d.pid : ""}</span>`).join("")}</div>` : ""}
      </div>`;
    })
    .join("");
}

/* ---------------- 方案弹窗 ---------------- */
function openModal(title, sub) {
  $("#modalTitle").textContent = title;
  $("#modalSub").textContent = sub || "";
  $("#modal").hidden = false;
  document.body.style.overflow = "hidden";
}
function closeModal() {
  $("#modal").hidden = true;
  $("#modalBody").innerHTML = "";
  document.body.style.overflow = "";
}

function openDraftModal(d) {
  const c = d.content;
  openModal(d.title_cn, `${d.category_cn} · 供货价 ¥${d.supply_price} · 提示词 ${c?.prompt_version || "—"}`);
  if (!c) {
    $("#modalBody").innerHTML = `<div class="empty"><p>该草稿没有方案内容</p></div>`;
    return;
  }
  const sec = (title, note, body) => `
    <div class="sec">
      <h4>${title}${note ? `<em>${note}</em>` : ""}</h4>
      ${body}
    </div>`;

  const titleSec = sec(
    "1 · 中英对照标题",
    `${c.title.letters} letters`,
    `<div class="copyline"><div class="zh">${esc(c.title.en)}</div><div class="en">${esc(c.title.cn)}</div></div>
     <div class="tline">规则校验：核心词前置 <b>✓</b> · 无标点 <b>✓</b> · ≤115 字母 <b>✓</b></div>`
  );

  const descSec = sec(
    "2 · 三套双语产品简介",
    "详情页可直接复制",
    c.descriptions
      .map(
        (x) => `<div class="copyline"><div class="zh"><strong>${esc(x.style)}</strong>｜${esc(x.zh)}</div><div class="en">${esc(x.en)}</div></div>`
      )
      .join("")
  );

  const bulletSec = sec(
    "3 · 五点 Bullet Points",
    "中英双语",
    `<ol class="sec-list">${c.bullets.map((b) => `<li>${esc(b.zh)}<div class="en" style="color:#5b6478;font-size:11.5px">${esc(b.en)}</div></li>`).join("")}</ol>`
  );

  const imgSec = sec(
    "4 · 6 张主副图规划",
    "800×800",
    `<div class="imgplan">${c.images
      .map(
        (im) => `<div class="item"><div class="no">0${im.no} · ${esc(im.type)}</div><div class="d">${esc(im.zh)}</div><div class="d" style="color:#98a2b3">${esc(im.en)}</div></div>`
      )
      .join("")}</div>`
  );

  const wordsSec = sec(
    "5 · 搜索词库",
    "标题埋词 + 后台关键词",
    `<div class="chips">${[...c.search_terms.title_words, ...c.search_terms.backend]
      .map((w) => `<span class="chipword">${esc(w)}</span>`)
      .join("")}</div>`
  );

  const compSec = sec("6 · 合规与运营提示", "欧美市场", `<ul class="sec-list">${c.compliance.map((x) => `<li>${esc(x)}</li>`).join("")}</ul>`);

  const attrSec = sec(
    "7 · 产品自定义属性",
    "中英对照",
    `<table class="attr-table"><thead><tr><th>属性</th><th>Attribute</th><th>值</th><th>Value</th></tr></thead><tbody>
      ${c.attrs
        .map(
          (a) => `<tr><td>${esc(a.name_zh)}</td><td>${esc(a.name_en)}</td><td>${esc(a.value_zh)}</td><td>${esc(a.value_en)}</td></tr>`
        )
        .join("")}
    </tbody></table>`
  );

  $("#modalBody").innerHTML = titleSec + descSec + bulletSec + imgSec + wordsSec + compSec + attrSec;
}

async function openPromptModal() {
  openModal("提示词模板全文", "速卖通欧美站 · 全托管上架全套方案 v1");
  $("#modalBody").innerHTML = `<div class="empty"><p>加载中…</p></div>`;
  try {
    const res = await api("/api/prompt");
    $("#modalBody").innerHTML = `<pre class="prompt-text">${esc(res.text)}</pre>`;
  } catch (e) {
    $("#modalBody").innerHTML = `<div class="empty"><p>读取失败：${esc(e.message)}</p></div>`;
  }
}

/* ---------------- 数据 ---------------- */
async function refreshData() {
  const data = await api("/api/bootstrap");
  S.drafts = data.drafts;
  S.tasks = data.tasks;
  S.stats = data.stats;
  S.usage = data.usage || S.usage;
  S.settings = data.settings;
  $("#reviewBadge").textContent = data.stats.pending + data.stats.approved;

  // 浏览器调试端口自检：没连上就顶部提示，避免客户一脸问号
  checkBrowser(true);
  setInterval(() => checkBrowser(true), 15000);
  checkModel();
  setInterval(checkModel, 20000);
  $("#statPending").textContent = data.stats.pending;
  $("#statApproved").textContent = data.stats.approved;
  $("#statSubmitted").textContent = data.stats.submitted;
  $("#statOnSale").textContent = data.stats.on_sale;
  if (S.view !== "settings") applySettings();
  if (S.view === "review") renderReview();
  if (S.view === "tasks") renderTasks();
}

function applySettings() {
  if (!S.settings) return;
  const st = S.settings;
  const L = st.llm || {};
  $("#storeName").textContent = st.store?.name || "未绑定店铺";
  const model = L.model || "";
  $("#modelName").textContent = /doubao/i.test(model) ? "豆包 Seed 1.6" : model || "未配置模型";
  $("#setStore").value = st.store?.name || "";
  $("#setExpire").value = st.store?.expire || "";
  $("#setProvider").value = L.provider || "volcengine";
  $("#setModel").value = model;
  $("#setBaseUrl").value = L.base_url || "";
  $("#setApiKey").value = L.api_key || "";
  $("#setFallback").value = L.fallback?.provider || "deepseek";
  $("#setFallbackModel").value = L.fallback?.model || "";
  $("#setTaskCopy").value = L.tasks?.copy || "";
  $("#setTaskCategory").value = L.tasks?.category || "";
  $("#usageText").textContent = `今日 ${S.usage.calls} 次 · 预估 ¥${Number(S.usage.est_cost).toFixed(2)}`;
  const SEL = st.selection || {};
  $("#setSelCount").value = SEL.count ?? 3;
  $("#setSelSales").value = SEL.min_sales ?? 3000;
  $("#setSelMin").value = SEL.price_min ?? 5;
  $("#setSelMax").value = SEL.price_max ?? 150;
  $("#set1688Key").value = st.a1688?.app_key || "";
}

/* ---------------- 模型状态灯 ---------------- */
async function checkModel() {
  const bar = $("#modelBar");
  if (!bar) return;
  try {
    const r = await api("/api/model/status");
    if (!r.configured) {
      bar.style.display = "flex";
      bar.style.background = "#fffaeb";
      bar.style.borderBottomColor = "#fedf89";
      bar.style.color = "#93370d";
      const t = $("#modelBarText");
      if (t) t.textContent = "还没配置大模型 Key，智能对话与选品都用不了。填一个 DeepSeek Key 即可（设置 → 模型）。";
      return;
    }
    if (r.last_error) {
      bar.style.display = "flex";
      bar.style.background = "#fef3f2";
      bar.style.borderBottomColor = "#fecdca";
      bar.style.color = "#b42318";
      const t = $("#modelBarText");
      if (t) t.textContent = `最近一次调用失败：${String(r.last_error).slice(0, 90)}`;
      return;
    }
    bar.style.display = "none";
  } catch (e) {
    bar.style.display = "none";
  }
}

/* ---------------- 浏览器调试端口状态 ---------------- */
async function checkBrowser(silent = true) {
  const bar = $("#browserBar");
  if (!bar) return;
  try {
    const r = await api("/api/browser/status");
    const alive = r && (r.debug_alive || r.ok);
    if (alive) { bar.style.display = "none"; return false; }
    bar.style.display = "flex";
  } catch (e) {
    bar.style.display = "flex";
  }
  if (!silent) toast("仍未连接：点上面「自动启动浏览器」，或手动运行 2-启动服务.bat");
  return true;
}

async function launchBrowser() {
  const btn = $("#browserLaunch");
  if (btn) { btn.disabled = true; btn.textContent = "启动中…"; }
  try {
    const r = await api("/api/browser/launch", { method: "POST", body: { port: 9222 } });
    if (!r.ok) { toast(r.message || "启动失败"); return; }
    // 轮询等待端口就绪
    for (let i = 0; i < 12; i++) {
      await new Promise((res) => setTimeout(res, 1000));
      const st = await api("/api/browser/status").catch(() => ({}));
      if (st && (st.debug_alive || st.ok)) {
        $("#browserBar").style.display = "none";
        toast("浏览器已连接。请在那个 Chrome 窗口里登录妙手ERP、1688");
        return;
      }
    }
    toast("浏览器已启动但端口还没就绪，稍等几秒再点「我已启动，重试」");
  } catch (e) {
    toast(`启动失败：${e.message}`);
  } finally {
    if (btn) { btn.disabled = false; btn.textContent = "自动启动浏览器"; }
  }
}

/* ---------------- 引导条 ---------------- */
function renderGuide() {
  const bar = $("#guideBar");
  if (!bar) return;
  const total = (S.drafts || []).length;
  const collected = (S.drafts || []).filter((d) => d.ms_detail_id).length;
  const qualified = (S.drafts || []).filter((d) => d.status === "approved").length;
  const steps = bar.querySelectorAll(".g-step");
  let active = 1, text = "";

  if (!total) {
    active = 1;
    text = '还没有商品。去「对话工作台」说一句，比如「选 3 款车载支架」，我来选品并生成草稿。';
  } else if (!collected) {
    active = 1;
    text = `有 ${total} 个草稿还没进妙手，点「① 采集到妙手」，我一次性送进公共采集箱（自动去重）。`;
  } else if (collected < total) {
    active = 1;
    text = `${collected}/${total} 个已进妙手，还有 ${total - collected} 个没采，再点一次「① 采集到妙手」。`;
  } else if (!qualified) {
    active = 2;
    text = `全部 ${total} 个已在「公共采集箱」。这里只有标题和图片，没有属性可翻——先点「② 打开妙手认领」到速卖通全托管，之后「③ 属性转英文」才有效。`;
  } else {
    active = 3;
    text = '已认领。到妙手打开商品编辑页，点「③ 属性转英文」，再去选 8 个类目属性并发布。';
  }

  steps.forEach((el) => {
    el.classList.toggle("done", Number(el.dataset.step) < active);
    el.classList.toggle("active", Number(el.dataset.step) === active);
  });
  const t = $("#guideText");
  if (t) t.textContent = text;
}

/* ---------------- 初始化 ---------------- */
/** 安全绑定：元素不存在时静默跳过，避免一个按钮缺失就让整页初始化失败 */
function bind(id, ev, fn) {
  const el = document.getElementById(id);
  if (!el) { console.warn("[bind] 缺少元素 #" + id); return; }
  el.addEventListener(ev, fn);
}

const REQUIRED_IDS = [
  "chatList", "input", "sendBtn", "reviewList", "guideBar", "guideText",
  "msApiBtn", "msClaimBtn", "msAttrEnBtn", "publishBtn", "logsBtn",
  "selAllBtn", "delSelBtn",
];

function checkLayout() {
  const missing = REQUIRED_IDS.filter((id) => !document.getElementById(id));
  if (!missing.length) return true;
  const bar = document.createElement("div");
  bar.style.cssText = "position:fixed;left:0;right:0;top:0;z-index:9999;background:#b42318;color:#fff;padding:10px 16px;font-size:13px;";
  bar.textContent = `界面文件版本不一致（缺少：${missing.join(", ")}）。请按 Ctrl+F5 强制刷新；仍不行说明文件未更新完整。`;
  document.body.prepend(bar);
  console.error("[layout] missing ids:", missing);
  return false;
}

async function init() {
  if (!checkLayout()) return;
  const data = await api("/api/bootstrap");
  S.settings = data.settings;
  S.drafts = data.drafts;
  S.tasks = data.tasks;
  S.stats = data.stats;
  S.usage = data.usage || S.usage;
  await loadProviders();
  applySettings();
  $("#reviewBadge").textContent = data.stats.pending + data.stats.approved;

  if (data.logs && data.logs.length) {
    data.logs.forEach(renderMessage);
  } else {
    renderMessage(welcome());
  }

  $("#sendBtn").addEventListener("click", () => send());
  $("#input").addEventListener("keydown", (e) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      send();
    }
  });
  $("#input").addEventListener("input", autoGrow);
  $$("#suggest button").forEach((b) => b.addEventListener("click", () => send(b.dataset.q)));
  $$(".nav-item").forEach((b) => b.addEventListener("click", () => switchView(b.dataset.view)));

  function syncSelBtns() {
    const n = S.picked ? S.picked.size : 0;
    const b = $("#delSelBtn");
    if (b) b.textContent = n ? `删除所选（${n}）` : "删除所选";
    const all = $("#selAllBtn");
    if (all) all.textContent = n ? "取消全选" : "全选本页";
  }

  bind("selAllBtn", "click", () => {
    if (!S.picked) S.picked = new Set();
    const ids = Array.from(document.querySelectorAll("[data-pick]")).map((c) => c.dataset.pick);
    if (S.picked.size) S.picked.clear();
    else ids.forEach((i) => S.picked.add(i));
    renderReview();
    syncSelBtns();
  });

  bind("delSelBtn", "click", async () => {
    const ids = Array.from(S.picked || []);
    if (!ids.length) return toast("还没选商品，先勾选或点「全选本页」");
    if (!confirm(`删除选中的 ${ids.length} 个草稿？不可恢复。`)) return;
    try {
      const r = await api("/api/drafts/delete", { method: "POST", body: { ids } });
      S.picked.clear();
      await refreshData();
      renderReview();
      toast(`已删除 ${r.deleted} 个`);
    } catch (e) {
      toast(`删除失败：${e.message}`);
    }
  });

  $("#approveAllBtn").addEventListener("click", async () => {
    const ids = S.drafts.filter((d) => d.status === "pending").map((d) => d.id);
    if (!ids.length) return toast("没有待审核的草稿");
    await api("/api/drafts/approve", { method: "POST", body: { ids } });
    await refreshData();
    renderReview();
    toast(`已确认 ${ids.length} 个`);
  });

  $("#erpPushBtn").addEventListener("click", async () => {
    const ids = S.drafts.filter((d) => d.status === "approved" || d.status === "pending").map((d) => d.id);
    if (!ids.length) return toast("没有可推送的草稿");
    if (!confirm(`把 ${ids.length} 个商品推送到店小宝采集箱？（只做采集，不发布）`)) return;
    try {
      const r = await api("/api/erp/push", { method: "POST", body: { draft_ids: ids, dry_run: true } });
      const blocked = (r.blocked || []).length;
      toast(
        r.ok
          ? `${(r.steps || []).join(" → ") || "已推送"}${blocked ? `（${blocked} 个需资质已拦截）` : ""}`
          : `推送失败：${r.message}`
      );
    } catch (e) {
      toast(`推送失败：${e.message}（先点一次「打开店小宝」并登录）`);
    }
  });

  // 取「勾选的」；没勾选才退回全部待处理
  function targetIds(extraFilter) {
    const all = S.drafts.filter((d) => {
      const st = d.status === "approved" || d.status === "pending";
      return st && (!extraFilter || extraFilter(d));
    });
    const picked = S.picked instanceof Set ? Array.from(S.picked) : [];
    if (picked.length) {
      const ids = all.filter((d) => picked.includes(d.id)).map((d) => d.id);
      return { ids, usedPicked: true, total: all.length };
    }
    return { ids: all.map((d) => d.id), usedPicked: false, total: all.length };
  }

  // ① 一键：采集 + 写入英文（标题用提示词规则生成的那版）
  $("#msApiBtn").addEventListener("click", async () => {
    const t = targetIds((d) => !!(d.source_url || d.url));
    const ids = t.ids;
    if (!ids.length) {
      return toast(t.usedPicked ? "勾选的商品里没有带 1688 链接的草稿" : "没有可采集的草稿（需要带 1688 链接）");
    }
    if (ids.length > 50) return toast("单次最多 50 条，请分批");
    const scope = t.usedPicked
      ? `已勾选 ${ids.length} 条`
      : `未勾选，将处理全部 ${ids.length} 条`;
    if (!confirm(`${scope}？\n1) 采集进妙手公共采集箱\n2) 用「提示词规则生成的英文标题」覆盖\n3) 描述/颜色名翻成英文`)) return;

    const btn = $("#msApiBtn");
    if (btn) { btn.disabled = true; btn.textContent = "处理中…"; }
    try {
      const r = await api("/api/erp/miaoshou/pipeline", { method: "POST", body: { draft_ids: ids } });
      if (r.ok) {
        toast(`采集 ${r.collected} 条，写入英文 ${r.done} 条。下一步：点「② 认领到全托管」`);
      } else {
        toast(`未完成：${r.message}${(r.failed && r.failed[0]) ? "（" + r.failed[0].msg + "）" : ""}`);
      }
      await refreshData();
      renderReview();
    } catch (e) {
      toast(`失败：${e.message}`);
    } finally {
      if (btn) { btn.disabled = false; btn.textContent = "① 采集＋英文（一键）"; }
    }
  });

  // 仅采集（不翻译）
  $("#msCollectOnlyBtn").addEventListener("click", async () => {
    const t = targetIds((d) => !!(d.source_url || d.url));
    const ids = t.ids;
    if (!ids.length) return toast("没有可采集的草稿");
    const scope = t.usedPicked ? `已勾选 ${ids.length} 条` : `未勾选，将处理全部 ${ids.length} 条`;
    if (!confirm(`${scope}，只采集不写英文？`)) return;
    try {
      const r = await api("/api/erp/miaoshou/api_collect", { method: "POST", body: { draft_ids: ids } });
      toast(r.ok ? `已采集 ${r.created} 条` : `失败：${r.message}`);
      await refreshData(); renderReview();
    } catch (e) {
      toast(`失败：${e.message}`);
    }
  });

  const ms = $("#modelBarSettings");
  if (ms) ms.addEventListener("click", (e) => { e.preventDefault(); switchView("settings"); });

  const bl = $("#browserLaunch");
  if (bl) bl.addEventListener("click", launchBrowser);

  const br = $("#browserRetry");
  if (br) br.addEventListener("click", async () => {
    br.disabled = true; br.textContent = "检测中…";
    await checkBrowser(false);
    br.disabled = false; br.textContent = "我已启动，重试";
  });

  $("#imgGenBtn").addEventListener("click", async () => {
    const st = await api("/api/images/status").catch(() => ({}));
    if (!st.enabled) {
      return toast("生图未启用：在设置里填火山方舟 Key 与模型即可（无需 Agent 套餐）");
    }
    const d = S.drafts.find((x) => x.status === "pending" || x.status === "approved");
    if (!d) return toast("没有可生成的草稿");
    if (!confirm(`给「${d.title_cn.slice(0, 16)}」生成一张场景图？\n（生图按张计费）`)) return;
    const btn = $("#imgGenBtn");
    if (btn) { btn.disabled = true; btn.textContent = "生成中…"; }
    try {
      const r = await api("/api/images/generate", { method: "POST", body: { draft_id: d.id, image_type: "场景图" } });
      toast(r.ok ? `已生成：${r.url}` : `失败：${r.message}`);
    } catch (e) {
      toast(`失败：${e.message}`);
    } finally {
      if (btn) { btn.disabled = false; btn.textContent = "生成场景图"; }
    }
  });

  $("#imgTrBtn").addEventListener("click", async () => {
    if (!confirm("把草稿里的商品图翻成英文（中文文字会被覆盖翻译）？\n\n首次会消耗妙手 AI 额度，建议先用 1 条试。")) return;
    const btn = $("#imgTrBtn");
    if (btn) { btn.disabled = true; btn.textContent = "翻译中…"; }
    try {
      const r = await api("/api/erp/miaoshou/translate_images", { method: "POST", body: { limit_per_item: 6 } });
      toast(r.ok
        ? `${r.message}。下一步：点「① 采集到妙手」，图片会用英文版`
        : `没翻到图：${r.message || "可能这些图没有文字"}`);
      await refreshData();
      renderReview();
    } catch (e) {
      toast(`失败：${e.message}`);
    } finally {
      if (btn) { btn.disabled = false; btn.textContent = "图片翻译（AI）"; }
    }
  });

  $("#msClaimBtn").addEventListener("click", async () => {
    const btn = $("#msClaimBtn");
    if (!confirm("把公共采集箱里「未认领」的商品全部认领到速卖通全托管？\n（会占用浏览器约 30 秒）")) return;
    if (btn) { btn.disabled = true; btn.textContent = "认领中…"; }
    try {
      const r = await api("/api/erp/miaoshou/claim", { method: "POST", body: { dry_run: false } });
      if (r.ok) {
        toast(`已认领 ${r.claimed} 条到速卖通全托管。下一步：点「③ 属性转英文」`);
      } else if (r.nothing) {
        toast(`${r.message}。可以去「速卖通全托管采集箱」直接翻译属性`);
      } else {
        toast(`认领未完成：${r.message}。可在「更多 → 打开采集箱」手工处理`);
      }
      await refreshData();
      renderReview();
    } catch (e) {
      toast(`认领失败：${e.message}（先启动调试 Chrome 并登录妙手）`);
    } finally {
      if (btn) { btn.disabled = false; btn.textContent = "② 认领到全托管"; }
    }
  });

  $("#msWriteEnBtn").addEventListener("click", async () => {
    let pre;
    try {
      pre = await api("/api/erp/miaoshou/write_en", { method: "POST", body: { dry_run: true } });
    } catch (e) {
      return toast(`预检失败：${e.message}`);
    }
    if (!pre.done) return toast(`没有需要翻译的商品（${pre.skipped} 条已是英文）`);
    if (!confirm(`会用妙手文本翻译把 ${pre.done} 条商品的标题/描述/颜色名改成英文（不花图片额度）。\n继续？`)) return;
    const btn = $("#msWriteEnBtn");
    if (btn) { btn.disabled = true; btn.textContent = "写入中…"; }
    try {
      const r = await api("/api/erp/miaoshou/write_en", { method: "POST", body: { dry_run: false } });
      toast(r.ok ? `${r.message}。下一步：认领到全托管，英文会带过去` : `部分失败：${(r.errors[0] || {}).msg || r.message}`);
    } catch (e) {
      toast(`失败：${e.message}`);
    } finally {
      if (btn) { btn.disabled = false; btn.textContent = "采集箱写英文"; }
    }
  });

  $("#msOpenBoxBtn").addEventListener("click", async () => {
    try {
      const r = await api("/api/erp/miaoshou/open_box", { method: "POST", body: { which: "common" } });
      toast(r.ok ? "已打开公共采集箱，手工勾选后点「认领到 → 速卖通全托管」" : "打开失败，检查调试 Chrome 登录状态");
    } catch (e) {
      toast(`打开失败：${e.message}`);
    }
  });

  $("#msAttrEnBtn").addEventListener("click", async () => {
    if (!confirm("把妙手编辑页「自定义属性」里的中文键值翻成英文并写回？（写完后记得在妙手点保存）")) return;
    const btn = $("#msAttrEnBtn");
    if (btn) { btn.disabled = true; btn.textContent = "翻译中…"; }
    try {
      const r = await api("/api/erp/miaoshou/custom_attrs", { method: "POST", body: { dry_run: false } });
      if (r.ok) {
        toast(`${r.message}。下一步：在妙手选 8 个类目属性 → 保存 → 发布`);
      } else if (/编辑页|自定义属性/.test(r.message || "")) {
        // 没打开编辑页：自动跳到全托管采集箱，并告诉用户点哪
        await api("/api/erp/miaoshou/open_box", { method: "POST", body: { which: "fc" } }).catch(() => {});
        toast("没有可翻译的商品编辑器。已打开「速卖通全托管采集箱」——如果里面是 0 条，说明还没认领：先在公共采集箱勾选商品 → 认领到速卖通全托管，再点商品「编辑」，最后点「③ 属性转英文」");
      } else {
        toast(`失败：${r.message}`);
      }
    } catch (e) {
      toast(`失败：${e.message}`);
    } finally {
      if (btn) { btn.disabled = false; btn.textContent = "属性转英文"; }
    }
  });

  $("#msPushBtn").addEventListener("click", async () => {
    const ids = S.drafts.filter((d) => d.status === "approved" || d.status === "pending").map((d) => d.id);
    if (!ids.length) return toast("没有可填入的草稿");
    if (!confirm(`把 ${ids.length} 个商品的链接+英文标题填进妙手采集框？（填完你去点「采集并自动认领」）`)) return;
    toast("正在填入妙手…");
    const btn = $("#msPushBtn");
    if (btn) { btn.disabled = true; btn.textContent = "填入中…"; }
    try {
      const r = await api("/api/erp/miaoshou/prepare", { method: "POST", body: { draft_ids: ids } });
      toast(r.ok ? `已填入 ${r.count} 条，去妙手页面点「采集并自动认领」` : `填入失败：${r.message}`);
    } catch (e) {
      toast(`失败：${e.message}（先启动调试 Chrome 并登录妙手）`);
    } finally {
      if (btn) { btn.disabled = false; btn.textContent = "填入妙手"; }
    }
  });

  $("#msCheckBtn").addEventListener("click", async () => {
    toast("正在读取妙手采集箱…");
    try {
      const r = await api("/api/erp/miaoshou/box");
      const rows = r.rows || [];
      const ids = rows
        .map((t) => (t.match(/货源[：:]\s*[（(]?\s*(\d{6,})/) || [])[1])
        .filter(Boolean);
      toast(r.ok ? `采集箱 ${rows.length} 条：${ids.slice(0, 5).join(", ")}` : "读取失败，检查妙手登录");
    } catch (e) {
      toast(`读取失败：${e.message}`);
    }
  });

  $("#publishBtn").addEventListener("click", async () => {
    const all = S.drafts.filter((d) => d.status === "approved");
    const picked = S.picked instanceof Set ? Array.from(S.picked) : [];
    const ids = (picked.length ? all.filter((d) => picked.includes(d.id)) : all).map((d) => d.id);
    if (!ids.length) return toast(picked.length ? "勾选的商品里没有「已确认」的" : "没有已确认的商品，先确认再提报");
    const scope = picked.length ? `已勾选 ${ids.length} 个` : `未勾选，将发布全部 ${ids.length} 个`;
    if (!confirm(`${scope}，在妙手「速卖通全托管采集箱」里发布？`)) return;
    toast("正在妙手里执行发布，约 25 秒…");
    try {
      const r = await api("/api/publish", { method: "POST", body: { ids } });
      toast(
        r.ok
          ? `发布已提交（命中 ${(r.found || []).length} 条），请到发布记录核对`
          : `发布未完成：${r.message || "请看妙手页面"}`
      );
      await refreshData();
      renderReview();
    } catch (e) {
      toast(`提报失败：${e.message}`);
    }
  });

  $("#logsBtn").addEventListener("click", openLogsModal);
  $("#viewPromptBtn").addEventListener("click", openPromptModal);
  $("#modalClose").addEventListener("click", closeModal);
  $("#modal").addEventListener("click", (e) => {
    if (e.target.dataset.close) closeModal();
  });
  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape") closeModal();
  });

  $("#saveBtn").addEventListener("click", async () => {
    const data = JSON.parse(JSON.stringify(S.settings));
    const fbProvider = providerById($("#setFallback").value);
    data.store.name = $("#setStore").value;
    data.llm = {
      provider: $("#setProvider").value,
      base_url: $("#setBaseUrl").value,
      model: $("#setModel").value,
      api_key: $("#setApiKey").value,
      fallback: {
        enabled: true,
        provider: $("#setFallback").value,
        base_url: fbProvider.base_url || "",
        model: $("#setFallbackModel").value,
        api_key: data.llm?.fallback?.api_key || "",
      },
      tasks: {
        copy: $("#setTaskCopy").value,
        vision: data.llm?.tasks?.vision || "",
        category: $("#setTaskCategory").value,
      },
    };
    data.a1688.app_key = $("#set1688Key").value;
    data.selection = {
      count: Number($("#setSelCount").value) || 3,
      min_sales: Number($("#setSelSales").value) || 0,
      price_min: Number($("#setSelMin").value) || 0,
      price_max: Number($("#setSelMax").value) || 9999,
      auto_confirm: true,
    };
    await api("/api/settings", { method: "POST", body: { data } });
    S.settings = data;
    applySettings();
    toast("设置已保存到本机");
  });

  $("#setProvider").addEventListener("change", () => {
    const p = providerById($("#setProvider").value);
    $("#setBaseUrl").value = p.base_url || "";
    if (p.models && p.models[0]) $("#setModel").value = p.models[0];
  });
  $("#setFallback").addEventListener("change", () => {
    const p = providerById($("#setFallback").value);
    if (p.models && p.models[0]) $("#setFallbackModel").value = p.models[0];
  });

  $("#testLlmBtn").addEventListener("click", async () => {
    const btn = $("#testLlmBtn");
    const msg = $("#testLlmMsg");
    btn.disabled = true;
    msg.className = "test-msg";
    msg.textContent = "测试中…";
    try {
      const r = await api("/api/llm/test", {
        method: "POST",
        body: {
          data: {
            provider: $("#setProvider").value,
            base_url: $("#setBaseUrl").value,
            model: $("#setModel").value,
            api_key: $("#setApiKey").value,
          },
        },
      });
      msg.className = `test-msg ${r.ok ? "ok" : "err"}`;
      msg.textContent = r.message;
    } catch (e) {
      msg.className = "test-msg err";
      msg.textContent = e.message;
    }
    btn.disabled = false;
  });

  $("#resetBtn").addEventListener("click", async () => {
    await api("/api/reset", { method: "POST" });
    S.logs = [];
    S.drafts = [];
    S.tasks = [];
    S.selected.clear();
    $("#chatList").innerHTML = "";
    renderMessage(welcome());
    await refreshData();
    renderReview();
    renderTasks();
    toast("演示数据已清空");
  });

  const hash = (location.hash || "").replace("#", "");
  if (VIEW_META[hash]) switchView(hash);

  const params = new URLSearchParams(location.search);
  if (params.get("demo") === "plan" && S.drafts.length) {
    switchView("review");
    setTimeout(() => openDraftModal(S.drafts[0]), 200);
  }
}

function autoGrow() {
  const el = $("#input");
  el.style.height = "auto";
  el.style.height = Math.min(130, el.scrollHeight) + "px";
}

init().catch((e) => {
  document.body.insertAdjacentHTML("beforeend", `<div style="position:fixed;left:20px;bottom:20px;background:#fee;color:#900;padding:10px 14px;border-radius:8px;font-size:12px">初始化失败：${esc(e.message)}</div>`);
});


/* ---------------- 日志面板 ---------------- */
async function openLogsModal() {
  openModal("运行日志", "最近 200 条，可一键打包提交");
  $("#modalBody").innerHTML = `<div class="empty"><p>加载中…</p></div>`;
  try {
    const res = await api("/api/logs?limit=200");
    const rows = (res.logs || [])
      .map(
        (l) =>
          `<div class="log-item"><time>${esc(l.time || "")}</time><b>${esc(
            l.role === "user" ? "你" : "Agent"
          )}</b><span>${esc((l.text || "").slice(0, 220))}</span></div>`
      )
      .join("");
    $("#modalBody").innerHTML = `
      <div class="log-list">${rows || "<p>暂无日志</p>"}</div>
      <div class="log-tools">
        <button class="btn primary" id="logSubmitBtn">打包提交</button>
        <button class="btn ghost" id="logRefreshBtn">刷新</button>
        <span style="color:#98a2b3;font-size:12px;align-self:center">文件：${esc(res.file || "")}</span>
      </div>`;
    $("#logRefreshBtn").addEventListener("click", openLogsModal);
    $("#logSubmitBtn").addEventListener("click", async () => {
      const note = window.prompt("补充说明（可留空）：", "") || "";
      toast("正在打包日志…");
      try {
        const r = await api("/api/logs/submit", { method: "POST", body: { note } });
        toast(r.message);
      } catch (e) {
        toast(`提交失败：${e.message}`);
      }
    });
  } catch (e) {
    $("#modalBody").innerHTML = `<div class="empty"><p>读取失败：${esc(e.message)}</p></div>`;
  }
}
