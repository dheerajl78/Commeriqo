const chatWindow = document.getElementById("chatWindow");
const chatForm = document.getElementById("chatForm");
const messageInput = document.getElementById("messageInput");
const promptButtons = document.querySelectorAll(".prompt");
const uciModeBtn = document.getElementById("uciModeBtn");
const statusPill = document.getElementById("statusPill");
const statusText = document.getElementById("statusText");
const memoryToggle = document.getElementById("memoryToggle");
const memoryBadge = document.getElementById("memoryBadge");

const API_URL = "http://127.0.0.1:8000/chat";
const HEALTH_URL = "http://127.0.0.1:8000/health";
let uciMode = false;
let memoryEnabled = false;
let typingEl = null;

const intentPrompts = {
  product_search: "Show me running shoes under 100",
  product_recommendation: "Recommend a camera for travel",
  order_tracking: "Track order 1234",
  refund_request: "I want a refund for order 1234",
  faq: "What is your return policy?",
  uci_package_help: "UCI package help for UCI-1001",
  greeting: "Hello",
};

function addMessage(
  text,
  sender = "bot",
  meta = "",
  agentLabel = "",
  confidence = null,
  intentSuggestions = null
) {
  const wrapper = document.createElement("div");
  wrapper.className = `message ${sender}`;

  const avatar = document.createElement("div");
  avatar.className = "avatar";
  avatar.textContent = sender === "user" ? "You" : "AI";

  const body = document.createElement("div");
  if (agentLabel) {
    const label = document.createElement("p");
    label.className = "meta";
    label.textContent = agentLabel;
    body.appendChild(label);
  }
  const p = document.createElement("p");
  p.className = "text";
  p.textContent = text;
  body.appendChild(p);

  if (meta) {
    const m = document.createElement("p");
    m.className = "meta";
    m.textContent = meta;
    body.appendChild(m);
  }

  if (typeof confidence === "number") {
    const meter = document.createElement("div");
    meter.className = "confidence-meter";
    const bar = document.createElement("div");
    bar.className = "confidence-bar";
    bar.style.width = `${Math.round(confidence * 100)}%`;
    if (confidence < 0.45) bar.classList.add("low");
    if (confidence >= 0.75) bar.classList.add("high");
    const label = document.createElement("span");
    label.textContent = `Confidence: ${(confidence * 100).toFixed(0)}%`;
    meter.appendChild(bar);
    meter.appendChild(label);
    body.appendChild(meter);
  }

  if (intentSuggestions && intentSuggestions.length) {
    const suggestionWrap = document.createElement("div");
    suggestionWrap.className = "intent-suggestions";
    intentSuggestions.forEach((s) => {
      const btn = document.createElement("button");
      btn.textContent = s.intent.replace("_", " ");
      btn.addEventListener("click", () => {
        const prompt = intentPrompts[s.intent] || s.intent;
        sendMessage(prompt);
      });
      suggestionWrap.appendChild(btn);
    });
    body.appendChild(suggestionWrap);
  }

  wrapper.appendChild(avatar);
  wrapper.appendChild(body);
  chatWindow.appendChild(wrapper);
  chatWindow.scrollTop = chatWindow.scrollHeight;
  return body;
}

function getPrefs() {
  try {
    return JSON.parse(localStorage.getItem("commeriqo_prefs")) || { products: {}, categories: {} };
  } catch (err) {
    return { products: {}, categories: {} };
  }
}

function setPrefs(prefs) {
  localStorage.setItem("commeriqo_prefs", JSON.stringify(prefs));
}

function updatePreference(product, weight = 1) {
  const prefs = getPrefs();
  prefs.products[product.id] = (prefs.products[product.id] || 0) + weight * 2;
  prefs.categories[product.category] = (prefs.categories[product.category] || 0) + weight;
  setPrefs(prefs);
}

function rankProducts(products) {
  const prefs = getPrefs();
  return [...products].sort((a, b) => {
    const aScore = (prefs.products[a.id] || 0) + (prefs.categories[a.category] || 0);
    const bScore = (prefs.products[b.id] || 0) + (prefs.categories[b.category] || 0);
    return bScore - aScore;
  });
}

function addProducts(products) {
  if (!products || !products.length) return;

  const list = document.createElement("div");
  list.className = "product-list";

  const ranked = rankProducts(products);
  ranked.forEach((p) => {
    const card = document.createElement("div");
    card.className = "product-card";
    const title = document.createElement("h4");
    title.textContent = `${p.name} · $${p.price}`;
    const desc = document.createElement("p");
    desc.textContent = `${p.category} • ${p.color}`;
    const actions = document.createElement("div");
    actions.className = "product-actions";
    const addBtn = document.createElement("button");
    addBtn.textContent = "Add to cart";
    addBtn.addEventListener("click", () => {
      updatePreference(p, 2);
      addMessage(`Added ${p.name} to your cart.`, "bot");
    });
    const saveBtn = document.createElement("button");
    saveBtn.textContent = "Save";
    saveBtn.addEventListener("click", () => {
      updatePreference(p, 1);
      addMessage(`Saved ${p.name} for later.`, "bot");
    });
    const compareBtn = document.createElement("button");
    compareBtn.textContent = "Compare";
    compareBtn.addEventListener("click", () => {
      updatePreference(p, 1);
      addMessage(`Added ${p.name} to comparison list.`, "bot");
    });
    actions.appendChild(addBtn);
    actions.appendChild(saveBtn);
    actions.appendChild(compareBtn);
    card.appendChild(title);
    card.appendChild(desc);
    card.appendChild(actions);
    list.appendChild(card);
  });

  chatWindow.appendChild(list);
  chatWindow.scrollTop = chatWindow.scrollHeight;
}

function addOrder(order) {
  if (!order) return;
  const card = document.createElement("div");
  card.className = "product-card";
  const title = document.createElement("h4");
  title.textContent = `Order ${order.order_id} · ${order.status}`;
  const desc = document.createElement("p");
  const items = Array.isArray(order.items) ? order.items.join(", ") : "N/A";
  desc.textContent = `ETA: ${order.eta} · Items: ${items}`;
  card.appendChild(title);
  card.appendChild(desc);
  chatWindow.appendChild(card);
  chatWindow.scrollTop = chatWindow.scrollHeight;
}

function showTyping() {
  if (typingEl) return;
  typingEl = document.createElement("div");
  typingEl.className = "typing";
  typingEl.innerHTML = "<span class='dot'></span><span class='dot'></span><span class='dot'></span> typing…";
  chatWindow.appendChild(typingEl);
  chatWindow.scrollTop = chatWindow.scrollHeight;
}

function hideTyping() {
  if (!typingEl) return;
  typingEl.remove();
  typingEl = null;
}

async function checkBackend() {
  try {
    const res = await fetch(HEALTH_URL);
    if (res.ok) {
      statusPill.classList.remove("offline");
      statusPill.classList.add("online");
      statusText.textContent = "Backend online";
      return;
    }
  } catch (err) {
    // ignore
  }
  statusPill.classList.remove("online");
  statusPill.classList.add("offline");
  statusText.textContent = "Backend offline";
}

async function sendMessage(message) {
  const finalMessage = uciMode ? `UCI package help: ${message}` : message;
  addMessage(message, "user", uciMode ? "UCI Receptionist Mode" : "");
  showTyping();

  try {
    const res = await fetch(API_URL, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({ message: finalMessage, session_id: memoryEnabled ? "memory-on" : null }),
    });

    if (!res.ok) {
      throw new Error("Server error");
    }

    const data = await res.json();
    const agentLabel = uciMode ? "UCI Receptionist" : "Commeriqo AI";
    addMessage(
      data.reply,
      "bot",
      `Intent: ${data.intent} (${data.confidence.toFixed(2)})`,
      agentLabel,
      data.confidence,
      data.intent_suggestions
    );
    addProducts(data.products);
    addOrder(data.order);
  } catch (err) {
    addMessage("I couldn't reach the server. Is the backend running?", "bot");
  } finally {
    hideTyping();
  }
}

chatForm.addEventListener("submit", (e) => {
  e.preventDefault();
  const text = messageInput.value.trim();
  if (!text) return;
  messageInput.value = "";
  sendMessage(text);
});

promptButtons.forEach((btn) => {
  btn.addEventListener("click", () => {
    const prompt = btn.dataset.prompt;
    if (prompt) {
      sendMessage(prompt);
    }
  });
});

uciModeBtn.addEventListener("click", () => {
  uciMode = !uciMode;
  uciModeBtn.textContent = uciMode ? "Exit UCI Receptionist" : "Connect to AI Receptionist";
  addMessage(
    uciMode
      ? "You're now connected to the UCI Package Receptionist. Share your UCI package ID (e.g., UCI-1001)."
      : "Exited UCI Receptionist mode. Back to main shopping assistant.",
    "bot"
  );
});

memoryToggle.addEventListener("click", () => {
  memoryEnabled = !memoryEnabled;
  memoryToggle.textContent = memoryEnabled ? "Disable Memory" : "Enable Memory";
  memoryBadge.textContent = memoryEnabled ? "Memory: On" : "Memory: Off";
  addMessage(memoryEnabled ? "Memory enabled for this session." : "Memory disabled.", "bot");
});

checkBackend();
setInterval(checkBackend, 5000);
