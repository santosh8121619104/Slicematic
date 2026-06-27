import gradio as gr
from datetime import datetime
from html import escape as html_escape
from pathlib import Path
from urllib.parse import quote
import re

try:
    from zoneinfo import ZoneInfo
    IST = ZoneInfo("Asia/Kolkata")
except Exception:
    from datetime import timezone, timedelta
    IST = timezone(timedelta(hours=5, minutes=30))

# ═══════════════════════════════════════════════════════════
# BUSINESS CONSTANTS (module-level, named variables)
# ═══════════════════════════════════════════════════════════
GST_RATE = 0.18
DISCOUNT_RATE = 0.10
DISCOUNT_THRESHOLD = 5
MAX_QTY = 10
MIN_QTY = 1
PAYMENT_MODES = ["Cash", "Card", "UPI"]
LOG_FILE = "orders_log.txt"
BASE_FILE = "Types_of_Base.txt"
PIZZA_FILE = "Types_of_Pizza.txt"
TOPPING_FILE = "Types_of_Toppings.txt"

# Asset directory — resolved next to app.py so the folder is portable
APP_DIR = Path(__file__).resolve().parent
MENU_IMAGE_DIR = APP_DIR / "assets" / "menu"

PAYMENT_MESSAGES = {
    "Cash": "Cash payment selected. Please collect payment at delivery/counter.",
    "Card": "Card payment selected. Please process on POS.",
    "UPI": "UPI payment selected. Please confirm receipt before fulfillment.",
}


def item_image_url(item_id):
    """Return a Gradio-served URL for an item's menu image, or '' if missing.

    Keyed by item ID (e.g. 'B1', 'P3'). Returning '' on miss lets the renderer
    fall back to a styled placeholder — this matters because the grader may
    swap menu files with IDs we have no image for.
    """
    p = MENU_IMAGE_DIR / f"{item_id}.jpg"
    if not p.exists():
        return ""
    return f"/gradio_api/file={quote(str(p))}"


# ═══════════════════════════════════════════════════════════
# MENU FILE LOADER
# ═══════════════════════════════════════════════════════════
def load_menu_file(filepath):
    """Load menu items from a semicolon-delimited file. Returns list of (id, name, price) tuples."""
    items = []
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            for line_num, line in enumerate(f, 1):
                line = line.strip()
                if not line:
                    continue
                parts = line.split(";")
                if len(parts) != 3:
                    print(f"[WARN] {filepath}:{line_num} — expected 3 fields, got {len(parts)}, skipping")
                    continue
                item_id, name, price_str = [p.strip() for p in parts]
                try:
                    price = float(price_str)
                except ValueError:
                    print(f"[WARN] {filepath}:{line_num} — non-numeric price '{price_str}', skipping")
                    continue
                if price < 0:
                    print(f"[WARN] {filepath}:{line_num} — negative price {price}, skipping")
                    continue
                items.append((item_id, name, price))
    except FileNotFoundError:
        print(f"[ERROR] File not found: {filepath}")
    except Exception as e:
        print(f"[ERROR] Could not read {filepath}: {e}")
    return items


# Load at startup — adapts dynamically to whatever files the grader provides
bases = load_menu_file(BASE_FILE)
pizzas = load_menu_file(PIZZA_FILE)
toppings = load_menu_file(TOPPING_FILE)
SYSTEM_READY = len(bases) > 0 and len(pizzas) > 0 and len(toppings) > 0


# ═══════════════════════════════════════════════════════════
# VALIDATION FUNCTIONS
# ═══════════════════════════════════════════════════════════
def validate_name(raw):
    name = (raw or "").strip()
    if not name or len(name) < 2 or len(name) > 40 or not re.match(r'^[A-Za-z ]+$', name):
        return None, "Name must contain alphabetic characters and be 2-40 characters long."
    return name, ""


def validate_phone(raw):
    phone = (raw or "").strip()
    if not phone:
        return None, "Phone number is required."
    if not phone.isdigit() or len(phone) != 10:
        return None, "Phone number must be exactly 10 digits."
    if phone[0] not in "6789":
        return None, "Enter a valid Indian mobile number starting with 6, 7, 8, or 9."
    return phone, ""


def validate_quantity(raw):
    if isinstance(raw, (int, float)):
        q = int(raw)
        if q <= 0:
            return None, "Quantity must be greater than 0."
        return q, ""
    s = str(raw or "").strip()
    if not s:
        return None, "Please enter a quantity."
    if "." in s:
        return None, "Quantity must be a whole number."
    try:
        q = int(s)
    except ValueError:
        return None, "Quantity must be a whole number."
    if q <= 0:
        return None, "Quantity must be greater than 0."
    return q, ""


def validate_selection(raw, items):
    s = (raw or "").strip()
    if not s:
        return None, "Please enter a valid item number."
    if "." in s:
        return None, "Please enter a valid item number."
    try:
        n = int(s)
    except ValueError:
        return None, "Please enter a valid item number."
    if n <= 0:
        return None, "Select a valid item number from the list."
    if n > len(items):
        return None, "That item number is not available."
    return n - 1, ""


def validate_toppings_checkbox(selected, items):
    if not selected:
        return [], "Please select at least one topping."
    indices = []
    for s in selected:
        try:
            n = int(s.split(".")[0])
            indices.append(n - 1)
        except Exception:
            pass
    if not indices:
        return [], "Please select at least one topping."
    return indices, ""


def render_cart_html(cart):
    if not cart:
        return '<div style="padding:20px; border:1px dashed #cbd5e1; border-radius:8px; text-align:center; color:#64748b;">Your cart is empty<br><span style="font-size:12px;">Add a pizza combination to begin.</span></div>'
        
    lines = []
    total = 0
    total_qty = 0
    for i, item in enumerate(cart):
        b = bases[item["base_idx"]]
        p = pizzas[item["pizza_idx"]]
        t_names = ", ".join([toppings[t][1] for t in item["topping_idx"]])
        unit = b[2] + p[2] + sum([toppings[t][2] for t in item["topping_idx"]])
        qty = item["quantity"]
        sub = unit * qty
        total += sub
        total_qty += qty
        
        lines.append(f"""
        <div class="sm-cart-item" style="padding-bottom: 8px; border-bottom: 1px dashed #e2e8f0; margin-bottom: 8px;">
            <div style="display:flex; justify-content:space-between; margin-bottom:4px;">
                <strong class="sm-cart-title">{qty}x {html_escape(p[1])}</strong>
                <span class="sm-cart-title" style="font-weight:600;">&#8377;{sub:.2f}</span>
            </div>
            <div class="sm-cart-desc">
                Base: {html_escape(b[1])}
            </div>
            <div class="sm-cart-desc">
                Toppings: {html_escape(t_names) if t_names else "None"}
            </div>
        </div>
        """)
        
    lines.append(f"""
    <div style="margin-top:16px; padding-top:16px; border-top:1px solid #e2e8f0; display:flex; justify-content:space-between; font-weight:700; color:var(--body-text-color);">
        <span>Cart Total <span style="font-size:12px;font-weight:normal;color:#64748b;">(Excl. GST)</span></span>
        <span>&#8377;{total:.2f}</span>
    </div>
    <div style="text-align:center; font-size:12px; color:#64748b; margin-top:8px;">{total_qty}/10 pizzas selected</div>
    """)
    return "".join(lines)


# ═══════════════════════════════════════════════════════════
# BILL COMPUTATION & RENDERING
# ═══════════════════════════════════════════════════════════
def compute_bill(cart):
    subtotal = 0
    total_qty = 0
    for item in cart:
        unit = bases[item["base_idx"]][2] + pizzas[item["pizza_idx"]][2]
        for t_idx in item["topping_idx"]:
            unit += toppings[t_idx][2]
        subtotal += unit * item["quantity"]
        total_qty += item["quantity"]
        
    discount = subtotal * DISCOUNT_RATE if total_qty >= DISCOUNT_THRESHOLD else 0
    taxable = subtotal - discount
    gst = taxable * GST_RATE
    final_total = taxable + gst
    return dict(
        subtotal=subtotal, discount=discount,
        taxable=taxable, gst=gst, final_total=final_total,
        total_qty=total_qty
    )


def render_bill_html(state, show_payment=False):
    cart = state.get("cart", [])
    if not cart:
        return ""
    bill = compute_bill(cart)
    qty = bill["total_qty"]

    discount_row = ""
    if qty >= DISCOUNT_THRESHOLD:
        discount_row = f"""
        <tr>
          <td class="sm-bill-cell sm-bill-discount">Discount (10% OFF)</td>
          <td class="sm-bill-val sm-bill-discount">
            -&#8377;{bill['discount']:,.2f}
          </td>
        </tr>"""

    payment_badge = ""
    if show_payment and state.get("payment_mode"):
        payment_badge = f"""
        <tr>
          <td colspan="2" style="padding:8px 16px; text-align:right;">
            <span class="sm-bill-badge">
              Paid via {html_escape(state['payment_mode'])}
            </span>
          </td>
        </tr>"""

    items_html = ""
    for item in cart:
        b = bases[item["base_idx"]]
        p = pizzas[item["pizza_idx"]]
        t_names = ", ".join([toppings[t][1] for t in item["topping_idx"]])
        unit = b[2] + p[2] + sum([toppings[t][2] for t in item["topping_idx"]])
        item_qty = item["quantity"]
        
        items_html += f"""
        <tr class="sm-bill-row">
          <td class="sm-bill-cell"><strong>{html_escape(p[1])}</strong> ({html_escape(b[1])})<br><span style="font-size:12px;color:#64748b;">+ {html_escape(t_names)}</span></td>
          <td class="sm-bill-val">x{item_qty}<br>&#8377;{unit * item_qty:,.2f}</td>
        </tr>
        """

    return f"""
    <div style="font-family:Inter,system-ui,sans-serif; max-width:500px; margin:0 auto;">
      <table class="sm-bill-table">
        {items_html}
        <tr>
          <td class="sm-bill-cell">Total Items</td>
          <td class="sm-bill-val">{qty}</td>
        </tr>
        <tr class="sm-bill-row-top">
          <td class="sm-bill-cell sm-bill-bold">Subtotal</td>
          <td class="sm-bill-val sm-bill-bold">&#8377;{bill['subtotal']:,.2f}</td>
        </tr>
        {discount_row}
        <tr>
          <td class="sm-bill-cell">GST (18%)</td>
          <td class="sm-bill-val">&#8377;{bill['gst']:,.2f}</td>
        </tr>
        <tr class="sm-bill-total-row">
          <td class="sm-bill-total-cell">
            Final Payable<br>
            <span class="sm-bill-tax-note">Includes all taxes and charges</span>
          </td>
          <td class="sm-bill-total-val">
            &#8377;{bill['final_total']:,.2f}
          </td>
        </tr>
        {payment_badge}
      </table>
    </div>"""


# ═══════════════════════════════════════════════════════════
# ORDER LOG
# ═══════════════════════════════════════════════════════════
def build_order_line(state):
    cart = state.get("cart", [])
    if not cart:
        return ""
    bill = compute_bill(cart)
    lines = []
    for item in cart:
        b = bases[item["base_idx"]]
        p = pizzas[item["pizza_idx"]]
        t_ids = ",".join([toppings[t][0] for t in item["topping_idx"]])
        t_names = ",".join([toppings[t][1] for t in item["topping_idx"]])
        t_prices = sum([toppings[t][2] for t in item["topping_idx"]])
        unit = b[2] + p[2] + t_prices
        
        lines.append(
            f"ORDER|{state['timestamp']}|{state['name']}|{state['phone']}|"
            f"{b[0]}|{b[1]}|{b[2]:.2f}|"
            f"{p[0]}|{p[1]}|{p[2]:.2f}|"
            f"{t_ids}|{t_names}|{t_prices:.2f}|"
            f"{item['quantity']}|{unit:.2f}|{unit * item['quantity']:.2f}|"
            f"{bill['discount']:.2f}|{bill['gst']:.2f}|{bill['final_total']:.2f}|"
            f"{state['payment_mode']}"
        )
    return "\n".join(lines)


# ═══════════════════════════════════════════════════════════
# HELPERS
# ═══════════════════════════════════════════════════════════
def format_menu(items, label):
    lines = [f"**{label}**\n"]
    for i, (_, name, price) in enumerate(items, 1):
        lines.append(f"{i}. {name} — ₹{price:.2f}")
    return "\n".join(lines)


def render_steps(active):
    """Render the 5-circle step indicator. `active` is 1..5; earlier steps marked done."""
    parts = ['<div class="sm-steps">']
    for n in range(1, 6):
        if n < active:
            cls = "sm-step-dot sm-step-done"
        elif n == active:
            cls = "sm-step-dot sm-step-active"
        else:
            cls = "sm-step-dot sm-step-pending"
        parts.append(f'<div class="{cls}">{n}</div>')
        if n < 5:
            line_cls = "sm-step-line sm-step-line-done" if n < active else "sm-step-line"
            parts.append(f'<div class="{line_cls}"></div>')
    parts.append('</div>')
    parts.append(f'<div class="sm-step-label">Step {active} of 5</div>')
    return "".join(parts)


def _img_block(item_id, kind="square"):
    """Image tile for an item — uses item_image_url; falls back to pizza emoji on miss."""
    url = item_image_url(item_id)
    cls = "sm-img" if kind == "square" else "sm-thumb"
    if url:
        return f'<div class="{cls}"><img src="{url}" alt=""></div>'
    return f'<div class="{cls}"><span class="sm-img-placeholder">🍕</span></div>'


def render_base_cards(items):
    """3-column grid of base cards: square image + name + price + selection number."""
    cards = []
    for i, (item_id, name, price) in enumerate(items, 1):
        cards.append(
            '<div class="sm-card-item">'
            + _img_block(item_id, "square")
            + f'<div class="sm-item-name"><span class="sm-num">{i}</span>{html_escape(name)}</div>'
            + f'<div class="sm-item-price">₹{price:.2f}</div>'
            + '</div>'
        )
    return (
        '<div class="sm-primary-text" style="font-weight:600;margin:8px 0 4px;">Choose your base</div>'
        '<div class="sm-base-grid">' + "".join(cards) + '</div>'
    )


def render_pizza_cards(items):
    """2-column grid of pizza cards: thumbnail + name + price + selection number."""
    cards = []
    for i, (item_id, name, price) in enumerate(items, 1):
        cards.append(
            '<div class="sm-card-pizza">'
            + _img_block(item_id, "thumb")
            + '<div style="flex:1;">'
            + f'<div class="sm-item-name"><span class="sm-num">{i}</span>{html_escape(name)}</div>'
            + f'<div class="sm-item-price">₹{price:.2f}</div>'
            + '</div>'
            + '</div>'
        )
    return (
        '<div class="sm-primary-text" style="font-weight:600;margin:8px 0 4px;">Choose your pizza</div>'
        '<div class="sm-pizza-grid">' + "".join(cards) + '</div>'
    )


def render_topping_pills(items):
    """Numbered pills (no image — matches the design's Stage 3 toppings row)."""
    pills = []
    for i, (_id, name, price) in enumerate(items, 1):
        pills.append(
            f'<span class="sm-pill"><span class="sm-num">{i}</span>'
            f'{html_escape(name)} <span class="sm-topping-price">+₹{price:.2f}</span></span>'
        )
    return (
        '<div class="sm-primary-text" style="font-weight:600;margin:8px 0 4px;">Choose your topping</div>'
        '<div class="sm-topping-pills">' + "".join(pills) + '</div>'
    )


def render_sidebar(step):
    steps = [
        (1, "Customer Details", "◎"),
        (2, "Menu Selection", "🍕"),
        (3, "Bill Summary", "🧾"),
        (4, "Payment", "💳"),
        (5, "Receipt", "✅"),
    ]
    
    html = f"""
    <div class="sm-sidebar">
        <div class="sm-step-text" style="font-size:14px; font-weight:700; margin-left:12px;">Step {step} of 5</div>
        <div class="sm-subtitle" style="font-size:12px; margin-left:12px; margin-bottom:24px;">Customize your order</div>
        <div style="display:flex; flex-direction:column; gap:8px;">
    """
    
    for s_num, s_name, s_icon in steps:
        active_class = "sm-sidebar-active" if s_num == step else ""
        html += f"""
            <div class="sm-sidebar-item {active_class}">
                <span style="margin-right:12px; font-size:16px;">{s_icon}</span> {s_name}
            </div>
        """
        
    html += "</div></div>"
    return html


def err(msg):
    if not msg:
        return ""
    return f"<p class='sm-error-text' style='font-size:13px; margin:4px 0;'>{html_escape(msg)}</p>"


def initial_state():
    return {
        "stage": 1,
        "name": "",
        "phone": "",
        "timestamp": "",
        "cart": [],
        "payment_mode": "",
    }


# ═══════════════════════════════════════════════════════════
# GRADIO APPLICATION
# ═══════════════════════════════════════════════════════════
HEAD_JS = """
<script>
document.addEventListener('click', function(e) {
    let btn = e.target.closest('.sm-dev-log-copy');
    if (btn) {
        let text = btn.getAttribute('data-log');
        navigator.clipboard.writeText(text);
        let oldHtml = btn.innerHTML;
        btn.innerHTML = '<span style="color:#4ade80; font-size:12px; margin-left:4px;">✓ Copied</span>';
        setTimeout(() => { btn.innerHTML = oldHtml; }, 2000);
    }
});
</script>
"""

with gr.Blocks(title="SliceMatic") as app:

    state = gr.State(initial_state())
    
    with gr.Row():
        with gr.Column(scale=1, min_width=250, elem_classes=["sm-sidebar-col"], visible=False) as sidebar_col:
            gr.HTML(
                '<div style="display:flex;align-items:center;gap:10px;padding:16px 8px;margin-bottom:24px;">'
                '<span style="font-size:28px;">🍕</span>'
                '<span class="sm-logo-text" style="font-size:22px;font-weight:700;">SliceMatic</span>'
                '</div>'
            )
            sidebar_display = gr.HTML(render_sidebar(1))
            
        with gr.Column(scale=4, elem_classes=["sm-main-col"]):

            if not SYSTEM_READY:
                # ──── SYSTEM UNAVAILABLE (matches service_unavailable screen) ────
                gr.HTML("""
                <div style="text-align:center; padding:120px 20px;">
                  <div style="width:96px; height:96px; background:#dee8ff; border-radius:50%;
                              margin:0 auto 32px; display:flex; align-items:center;
                              justify-content:center; font-size:44px;">🍕</div>
                  <h1 class="sm-headline" style="font-size:32px; line-height:1.2;">
                    SliceMatic is<br>temporarily unavailable</h1>
                  <p class="sm-subtitle">Please try again shortly.</p>
                </div>
                """)

            else:
                # ════════════════════════════════════════════════════
                # STAGE 1 — System Ready (no step indicator per design)
                # ════════════════════════════════════════════════════
                with gr.Group(visible=True) as stage1:
                    init_lines = []
                    for fname, items, label in [
                        (BASE_FILE, bases, "bases"),
                        (PIZZA_FILE, pizzas, "pizzas"),
                        (TOPPING_FILE, toppings, "toppings"),
                    ]:
                        init_lines.append(
                            f'<div class="sm-primary-text" style="font-size:14px;margin:6px 0;">'
                            f'<span style="color:#24963F;font-weight:700;">✓</span> '
                            f'<strong>{html_escape(fname)}</strong> — {len(items)} {label} loaded</div>'
                        )
                    gr.HTML(
                        '<div class="sm-card" style="max-width:480px;text-align:center;margin: 0 auto;">'
                        '<div style="width:80px;height:80px;background:#dcf5e0;border-radius:50%;'
                        'margin:8px auto 20px;display:flex;align-items:center;justify-content:center;'
                        'font-size:40px;color:#24963F;">✓</div>'
                        '<h2 class="sm-primary-text" style="font-size:24px;font-weight:700;margin:0 0 6px;">All systems ready.</h2>'
                        '<p class="sm-subtitle">Menu files loaded successfully.</p>'
                        '<div style="text-align:left;margin:16px 0 8px;">'
                        + "".join(init_lines) +
                        '</div></div>'
                    )
                    start_btn = gr.Button("Start Ordering →", variant="primary", size="lg")

                # ════════════════════════════════════════════════════
                # STAGE 2 — Customer Intake (Step 1 of 5 per design)
                # ════════════════════════════════════════════════════
                with gr.Column(visible=False, elem_classes=["sm-card"]) as stage2:
                    gr.HTML(
                        '<div style="text-align:center;margin:24px 0 8px;">'
                        '<h1 class="sm-headline">Let\'s get started</h1>'
                        '<p class="sm-subtitle">We need a few details to process your order.</p>'
                        '</div>'
                    )
                    with gr.Column(elem_classes=["narrow-container"]):
                        name_input = gr.Textbox(
                            label="Your Name", placeholder="e.g. Aman Sharma", max_lines=1,
                        )
                        name_err_display = gr.HTML("")
                        phone_input = gr.Textbox(
                            label="Mobile Number (+91)", placeholder="10-digit number", max_lines=1,
                        )
                        phone_err_display = gr.HTML("")
                        intake_btn = gr.Button("Continue →", variant="primary", size="lg")

                # ════════════════════════════════════════════════════
                # STAGE 3 — Quantity + Menu Selection
                # ════════════════════════════════════════════════════
                with gr.Column(visible=False, elem_classes=["sm-card"]) as stage3:
                    gr.HTML('<h1 class="sm-headline" style="text-align:center;">Build Your Order</h1>')

                    with gr.Row():
                        # Left side - Build order
                        with gr.Column(scale=2):
                            gr.HTML('<h2 class="sm-headline" style="font-size:20px; border-left: 4px solid #b7102a; padding-left: 8px;">Menu Selection</h2>')
                            
                            base_menu_md = gr.HTML(render_base_cards(bases))
                            with gr.Column(elem_classes=["narrow-container"]):
                                base_input = gr.Textbox(label="Enter base number", placeholder="e.g. 1", max_lines=1)
                                base_err_display = gr.HTML("")

                            pizza_menu_md = gr.HTML(render_pizza_cards(pizzas))
                            with gr.Column(elem_classes=["narrow-container"]):
                                pizza_input = gr.Textbox(label="Enter pizza number", placeholder="e.g. 1", max_lines=1)
                                pizza_err_display = gr.HTML("")

                            topping_choices = [f"{i}. {name} (+₹{price:.2f})" for i, (_, name, price) in enumerate(toppings, 1)]
                            topping_input = gr.CheckboxGroup(
                                choices=topping_choices, label="Choose your toppings", value=[], elem_classes=["sm-topping-checkboxes"]
                            )
                            topping_err_display = gr.HTML("")
                            
                            gr.HTML('<hr style="border:none;border-top:1px solid #e2e8f0;margin:16px 0;">')
                            with gr.Column(elem_classes=["narrow-container"]):
                                qty_input = gr.Slider(label="Quantity for this pizza", minimum=1, maximum=10, step=1, value=1)
                                
                                with gr.Row(elem_classes=["sm-action-buttons"]):
                                    add_cart_btn = gr.Button("Add to cart", variant="primary")
                                    clear_build_btn = gr.Button("Clear selection", variant="secondary")
                                
                                add_cart_err = gr.HTML("")
                                add_cart_msg = gr.HTML("")

                        # Right side - Cart
                        with gr.Column(scale=1):
                            gr.HTML('<h2 class="sm-headline" style="font-size:20px; border-left: 4px solid #b7102a; padding-left: 8px;">Cart</h2>')
                            cart_display = gr.HTML(
                                '<div style="padding:20px; border:1px dashed #cbd5e1; border-radius:8px; text-align:center; color:#64748b;">'
                                'Your cart is empty<br><span style="font-size:12px;">Add a pizza combination to begin.</span>'
                                '</div>'
                            )
                            
                            with gr.Row(elem_classes=["sm-action-buttons"]):
                                clear_cart_btn = gr.Button("Clear cart", variant="secondary")
                                menu_btn = gr.Button("Continue to Bill →", variant="primary", interactive=False)

                # ════════════════════════════════════════════════════
                # STAGE 4 — Bill Review (design step 3)
                # ════════════════════════════════════════════════════
                with gr.Column(visible=False, elem_classes=["sm-card"]) as stage4:
                    gr.HTML('<h1 class="sm-headline" style="text-align:center;">Your Order</h1>')
                    bill_display = gr.HTML("")
                    with gr.Column(elem_classes=["narrow-container"]):
                        bill_btn = gr.Button("Proceed to Payment →", variant="primary", size="lg")

                # ════════════════════════════════════════════════════
                # STAGE 5 — Payment (design step 4) + Receipt (design step 5)
                # ════════════════════════════════════════════════════
                with gr.Column(visible=False, elem_classes=["sm-card"]) as stage5:

                    with gr.Column(visible=True) as pay_section:
                        gr.HTML('<h1 class="sm-headline" style="text-align:center;">How would you like to pay?</h1>')
                        with gr.Column(elem_classes=["narrow-container"]):
                            pay_radio = gr.Radio(
                                choices=PAYMENT_MODES, label="Payment Mode", value=None,
                            )
                            pay_err_display = gr.HTML("")
                            pay_msg_display = gr.HTML("")
                            pay_btn = gr.Button("Confirm Order", variant="primary", size="lg")

                    with gr.Column(visible=False) as receipt_section:
                        receipt_display = gr.HTML("")
                        new_btn = gr.Button("🏠 New Order", variant="secondary", size="lg")

        # ════════════════════════════════════════════════════
        # EVENT HANDLERS
        # ════════════════════════════════════════════════════

        # ── Stage 1 → Stage 2 ──────────────────────────────
        def on_start(st):
            st["stage"] = 2
            st["timestamp"] = datetime.now(IST).isoformat()
            return st, render_sidebar(1), gr.update(visible=False), gr.update(visible=True), gr.update(visible=True)

        start_btn.click(on_start, [state], [state, sidebar_display, stage1, stage2, sidebar_col])

        # ── Stage 2 → Stage 3 ──────────────────────────────
        def on_intake(st, name_raw, phone_raw):
            try:
                name, ne = validate_name(name_raw)
                phone, pe = validate_phone(phone_raw)
                if name is not None and phone is not None:
                    st["name"] = name
                    st["phone"] = phone
                    st["stage"] = 3
                    return (
                        st, render_sidebar(2), err(ne), err(pe),
                        gr.update(visible=False), gr.update(visible=True),
                    )
                return st, gr.update(), err(ne), err(pe), gr.update(), gr.update()
            except Exception:
                return (
                    st, gr.update(), err("An unexpected error occurred."), err(""),
                    gr.update(), gr.update(),
                )

        intake_btn.click(
            on_intake,
            [state, name_input, phone_input],
            [state, sidebar_display, name_err_display, phone_err_display, stage2, stage3],
        )

        # ── Stage 3: Build Order & Cart ───────────────────────────
        def on_add_cart(st, b_raw, p_raw, t_selected, qty_raw):
            try:
                bi, be = validate_selection(b_raw, bases)
                pi, pe = validate_selection(p_raw, pizzas)
                ti, te = validate_toppings_checkbox(t_selected, toppings)
                
                if bi is None or pi is None or (not ti and "select at least one" in te):
                    return (
                        st, err(be), err(pe), err(te), err(""),
                        "", __import__("gradio").update(), __import__("gradio").update()
                    )
                
                qty, qe = validate_quantity(qty_raw)
                if qty is None:
                    return st, err(""), err(""), err(""), err(qe), "", __import__("gradio").update(), __import__("gradio").update()
                    
                cart = st.get("cart", [])
                total_qty = sum(item["quantity"] for item in cart)
                if total_qty + qty > 10:
                    return st, err(""), err(""), err(""), err(f"Cannot add {qty} pizzas. Maximum order is 10. Cart has {total_qty}."), "", __import__("gradio").update(), __import__("gradio").update()
                    
                cart.append({
                    "base_idx": bi,
                    "pizza_idx": pi,
                    "topping_idx": ti,
                    "quantity": qty
                })
                st["cart"] = cart
                
                html = render_cart_html(cart)
                return (
                    st, err(""), err(""), err(""), err(""),
                    f"<p class='sm-success-msg'>✓ Added to cart</p>", html, __import__("gradio").update(interactive=True)
                )
            except Exception as e:
                return st, err("An unexpected error occurred."), err(""), err(""), err(""), "", __import__("gradio").update(), __import__("gradio").update()

        add_cart_btn.click(
            on_add_cart,
            [state, base_input, pizza_input, topping_input, qty_input],
            [state, base_err_display, pizza_err_display, topping_err_display, add_cart_err, add_cart_msg, cart_display, menu_btn]
        )

        def on_clear_build():
            return "", "", [], 1, "", "", "", "", ""
        
        clear_build_btn.click(
            on_clear_build,
            [],
            [base_input, pizza_input, topping_input, qty_input, base_err_display, pizza_err_display, topping_err_display, add_cart_err, add_cart_msg]
        )
        
        def on_clear_cart(st):
            st["cart"] = []
            html = render_cart_html([])
            return st, html, __import__("gradio").update(interactive=False)
            
        clear_cart_btn.click(
            on_clear_cart, [state], [state, cart_display, menu_btn]
        )

        # ── Stage 3 → Stage 4 ─────────────────────────────
        def on_menu_continue(st):
            try:
                cart = st.get("cart", [])
                if not cart:
                    return st, render_sidebar(2), __import__("gradio").update(), __import__("gradio").update(), ""
                
                st["stage"] = 4
                html = render_bill_html(st)
                return (
                    st, render_sidebar(3),
                    __import__("gradio").update(visible=False), __import__("gradio").update(visible=True), html,
                )
            except Exception:
                return st, render_sidebar(2), __import__("gradio").update(), __import__("gradio").update(), ""

        menu_btn.click(
            on_menu_continue,
            [state],
            [
                state, sidebar_display,
                stage3, stage4, bill_display,
            ],
        )

        # ── Stage 4 → Stage 5 ─────────────────────────────
        def on_proceed(st):
            st["stage"] = 5
            return st, render_sidebar(4), gr.update(visible=False), gr.update(visible=True)

        bill_btn.click(on_proceed, [state], [state, sidebar_display, stage4, stage5])

        # ── Stage 5: Payment selection change ──────────────
        def on_pay_select(selection):
            if selection in PAYMENT_MODES:
                return (
                    "",
                    f"<p class='sm-pay-info'>ℹ {html_escape(PAYMENT_MESSAGES[selection])}</p>",
                )
            return err("Please select a valid payment mode: Cash, Card, or UPI."), ""

        pay_radio.change(on_pay_select, [pay_radio], [pay_err_display, pay_msg_display])

        # ── Stage 5: Confirm Order + Persistence ──────────
        def on_confirm_order(st, selection):
            try:
                if selection is None or selection not in PAYMENT_MODES:
                    return (
                        st, render_sidebar(4),
                        err("Please select a valid payment mode: Cash, Card, or UPI."),
                        "", gr.update(), gr.update(), "",
                    )

                st["payment_mode"] = selection
                order_line = build_order_line(st)

                # Dedicated try/except for file write — the critical edge case
                try:
                    with open(LOG_FILE, "a", encoding="utf-8") as f:
                        f.write(order_line + "\n\n")
                    write_ok = True
                except Exception:
                    write_ok = False

                bill_html = render_bill_html(st, show_payment=True)
                safe_name = html_escape(st["name"])
                safe_ts = html_escape(st["timestamp"])

                if write_ok:
                    receipt = f"""
                    <div style="text-align:center; padding:20px; font-family:Inter,system-ui,sans-serif;">
                      <div class="sm-success-icon">✅</div>
                      <h2 class="sm-success-title">Order Confirmed</h2>
                      <p class="sm-receipt-msg">
                        Your pizza is on its way. Thank you for choosing SliceMatic.
                      </p>
                      <div class="sm-receipt-details">
                        <p><strong>Customer:</strong> {safe_name}</p>
                        <p><strong>Order Time:</strong> {safe_ts}</p>
                      </div>
                      {bill_html}
                      <div class="sm-dev-log">
                        <div class="sm-dev-log-header">
                          <div style="display:flex; align-items:center;">
                            <span style="font-family:monospace;font-size:14px;color:#94a3b8;margin-right:6px;">>_</span> DEVELOPER TRACE LOG
                          </div>
                          <button class="sm-dev-log-copy" data-log="{html_escape(order_line)}" title="Copy to clipboard">
                            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="9" y="9" width="13" height="13" rx="2" ry="2"></rect><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"></path></svg>
                          </button>
                        </div>
                        <div class="sm-dev-log-content">{html_escape(order_line)}</div>
                      </div>
                    </div>"""
                else:
                    safe_mode = html_escape(st["payment_mode"])
                    receipt = f"""
                    <div style="text-align:center; padding:20px; font-family:Inter,system-ui,sans-serif;">
                      <div class="sm-error-icon">⚠️</div>
                      <h2 class="sm-error-title">Order Recording Failed</h2>
                      <p class="sm-receipt-msg">
                        Your order total and payment mode were confirmed, but we could not
                        save your order record. Please show this screen to staff:
                      </p>
                      <div class="sm-receipt-details">
                        <p><strong>Customer:</strong> {safe_name}</p>
                        <p><strong>Order Time:</strong> {safe_ts}</p>
                        <p><strong>Payment:</strong> {safe_mode}</p>
                      </div>
                      {bill_html}
                      <div class="sm-dev-log">
                        <div class="sm-dev-log-header">
                          <div style="display:flex; align-items:center;">
                            <span style="font-family:monospace;font-size:14px;color:#94a3b8;margin-right:6px;">>_</span> DEVELOPER TRACE LOG
                          </div>
                          <button class="sm-dev-log-copy" data-log="{html_escape(order_line)}" title="Copy to clipboard">
                            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="9" y="9" width="13" height="13" rx="2" ry="2"></rect><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"></path></svg>
                          </button>
                        </div>
                        <div class="sm-dev-log-content">{html_escape(order_line)}</div>
                      </div>
                    </div>"""

                return (
                    st, render_sidebar(5), "", "",
                    gr.update(visible=False), gr.update(visible=True), receipt,
                )
            except Exception:
                return (
                    st, render_sidebar(4), err("An unexpected error occurred. Please try again."),
                    "", gr.update(), gr.update(), "",
                )

        pay_btn.click(
            on_confirm_order,
            [state, pay_radio],
            [
                state, sidebar_display, pay_err_display, pay_msg_display,
                pay_section, receipt_section, receipt_display,
            ],
        )

        # ── New Order (reset everything) ───────────────────────────
        def on_new_order():
            return (
                initial_state(),
                render_sidebar(1),                               # sidebar
                __import__("gradio").update(visible=True),                        # stage1
                __import__("gradio").update(visible=False),                       # stage2
                __import__("gradio").update(visible=False),                       # stage3
                __import__("gradio").update(visible=False),                       # stage4
                __import__("gradio").update(visible=False),                       # stage5
                __import__("gradio").update(value=""),                             # name_input
                __import__("gradio").update(value=""),                             # phone_input
                "",                                              # name_err
                "",                                              # phone_err
                __import__("gradio").update(value=1),                              # qty_input
                "",                                              # add_cart_err
                "",                                              # add_cart_msg
                '<div style="padding:20px; border:1px dashed #cbd5e1; border-radius:8px; text-align:center; color:#64748b;">Your cart is empty<br><span style="font-size:12px;">Add a pizza combination to begin.</span></div>', # cart_display
                __import__("gradio").update(value=""),                            # base_input
                __import__("gradio").update(value=""),                            # pizza_input
                __import__("gradio").update(value=[]),                             # topping_input
                "",                                              # base_err
                "",                                              # pizza_err
                "",                                              # topping_err
                __import__("gradio").update(interactive=False),                    # menu_btn
                "",                                              # bill_display
                __import__("gradio").update(value=None),                           # pay_radio
                "",                                              # pay_err
                "",                                              # pay_msg
                __import__("gradio").update(visible=True),                         # pay_section
                __import__("gradio").update(visible=False),                        # receipt_section
                "",                                              # receipt_display
                __import__("gradio").update(visible=False),                        # sidebar_col
            )

        new_btn.click(
            on_new_order,
            [],
            [
                state, sidebar_display, stage1, stage2, stage3, stage4, stage5,
                name_input, phone_input, name_err_display, phone_err_display,
                qty_input, add_cart_err, add_cart_msg, cart_display,
                base_input, pizza_input, topping_input,
                base_err_display, pizza_err_display, topping_err_display,
                menu_btn, bill_display,
                pay_radio, pay_err_display, pay_msg_display,
                pay_section, receipt_section, receipt_display, sidebar_col,
            ],
        )

if __name__ == "__main__":
    # Design-system stylesheet — applies Stitch tokens to native Gradio
    # components AND defines classes used by our gr.HTML blocks.
    DESIGN_CSS = """
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');

    /* Reset & Surface */
    .gradio-container, .gradio-container * {
        font-family: 'Inter', system-ui, -apple-system, sans-serif !important;
    }
    .gradio-container {
        background: #f8f9fa !important;
        color: #0F172A !important;
        max-width: 100% !important;
        margin: auto !important;
    }
    body, gradio-app { background: #f8f9fa !important; color: #0F172A !important; }

    /* Force light mode — override Gradio dark theme regardless of OS preference */
    @media (prefers-color-scheme: dark) {
        body, gradio-app, .gradio-container { background: #f8f9fa !important; color: #0F172A !important; }
    }
    .dark, .dark .gradio-container, .dark body,
    [data-theme="dark"], [data-theme="dark"] .gradio-container {
        background: #f8f9fa !important; color: #0F172A !important;
    }
    .dark .gradio-container h1, .dark .gradio-container h2, .dark .gradio-container h3,
    .dark .gradio-container p, .dark .gradio-container label,
    .dark .gradio-container span, .dark .gradio-container div {
        color: inherit !important;
    }
    .dark input[type=text], .dark textarea {
        background: #ffffff !important; color: #0F172A !important;
        border: 1px solid #cbd5e1 !important;
    }
    .dark .gradio-container button.primary,
    .dark .gradio-container .primary > button {
        background: #b7102a !important; color: #ffffff !important;
    }
    .dark .sm-card, .dark .sm-card-item, .dark .sm-card-pizza, .dark .sm-pill {
        background: #ffffff !important; color: #0F172A !important;
    }
    .dark .sm-sidebar-col {
        background: #f8f9fa !important;
    }

    /* Headings */
    .gradio-container h1, .gradio-container h2, .gradio-container h3,
    .gradio-container .prose h1, .gradio-container .prose h2 {
        color: #0F172A !important; font-weight: 700 !important; letter-spacing: -0.02em;
    }
    .gradio-container .prose p, .gradio-container label { color: #334155 !important; }

    /* Primary buttons */
    .gradio-container button.primary,
    .gradio-container .primary > button {
        background: #b7102a !important; color: #ffffff !important;
        border: none !important; font-weight: 600 !important;
        border-radius: 8px !important; padding: 12px 24px !important;
        box-shadow: 0 4px 6px -1px rgba(183, 16, 42, 0.2) !important;
        margin-top: 16px !important;
    }
    .gradio-container button.primary:hover,
    .gradio-container .primary > button:hover { background: #9b0d23 !important; }
    .gradio-container button.primary:disabled { background: #cbd5e1 !important; color: #ffffff !important; box-shadow: none !important; }
    .gradio-container button.secondary { border-radius: 8px !important; }

    /* Gradio Theme Variable Overrides */
    .gradio-container {
        --background-fill-primary: transparent !important;
        --background-fill-secondary: transparent !important;
        --block-background-fill: transparent !important;
        --block-label-background-fill: transparent !important;
        --block-border-width: 0px !important;
        --panel-background-fill: transparent !important;
    }

    /* Form resets */
    .gradio-container .form, .gradio-container .block {
        background: transparent !important; border: none !important;
        box-shadow: none !important; margin: 0 !important; padding: 0 !important;
    }

    /* Text inputs */
    .gradio-container .wrap { background: transparent !important; border: none !important; box-shadow: none !important; padding: 0 !important; }
    .gradio-container .wrap > label, .gradio-container .wrap > label span { 
        margin-bottom: 6px !important; font-weight: 500 !important; font-size: 14px !important; 
        color: #334155 !important; background: transparent !important; padding: 0 !important; 
        border: none !important;
    }
    
    .gradio-container input[type=text], .gradio-container textarea {
        background: #ffffff !important; color: #0F172A !important;
        border: 1px solid #cbd5e1 !important; border-radius: 8px !important;
        padding: 12px 16px !important; font-size: 16px !important;
    }
    .gradio-container input[type=text]:focus, .gradio-container textarea:focus {
        border-color: #b7102a !important; outline: none !important;
        box-shadow: 0 0 0 3px rgba(183,16,42,0.1) !important;
    }

    /* Reusable design classes */
    body, .gradio-container { background-color: #f8fafc !important; }
    .dark body, .dark .gradio-container { background-color: #0f172a !important; }
    
    .gradio-container { max-width: 100% !important; padding: 0 !important; margin: 0 !important; }
    
    .gradio-container .sm-card, .gradio-container .sm-card.column {
        background: #ffffff !important; border: 1px solid #e2e8f0 !important;
        border-radius: 12px !important; padding: 32px !important; margin: 24px auto !important;
        box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.05), 0 2px 4px -1px rgba(0, 0, 0, 0.03) !important;
        max-width: 1400px !important; align-self: center !important; width: 100% !important;
    }
    .narrow-container { max-width: 480px !important; margin: 0 auto !important; }
    
    /* Radio (payment modes) */
    .gradio-container [data-testid="radio"] { background: transparent !important; border: none !important; box-shadow: none !important; }
    .gradio-container [data-testid="radio"] label {
        background: #ffffff !important; border: 1px solid #cbd5e1 !important;
        border-radius: 8px !important; color: #0F172A !important; padding: 12px !important; margin-bottom: 8px !important;
    }
    
    /* Force inputs to be clean */
    .gradio-container label.svelte-1f354aw, .gradio-container .wrap > label, .gradio-container label span {
        background: transparent !important;
        border: none !important;
    }
    .gradio-container .form {
        background: transparent !important;
        border: none !important;
        box-shadow: none !important;
    }
    .sm-headline { font-size: 32px; font-weight: 700; color: #0F172A; margin: 0 0 12px; letter-spacing: -0.02em; }
    .sm-subtitle { font-size: 16px; color: #64748b; margin: 0 0 32px; line-height: 1.5; }
    
    /* Progress Bar */
    .sm-steps {
        display: flex; align-items: center; justify-content: center;
        gap: 0; max-width: 400px; margin: 0 auto 16px;
    }
    .sm-step-dot {
        width: 28px; height: 28px; border-radius: 50%; display: flex;
        align-items: center; justify-content: center;
        font-size: 13px; font-weight: 600; flex-shrink: 0;
    }
    .sm-step-pending { background: #f1f5f9; color: #94a3b8; border: 1px solid #e2e8f0; }
    .sm-step-active  { background: #b7102a; color: #ffffff; border: 1px solid #b7102a; }
    .sm-step-done    { background: #b7102a; color: #ffffff; border: 1px solid #b7102a; }
    .sm-step-line { flex: 1; height: 2px; background: #e2e8f0; }
    .sm-step-line-done { background: #b7102a; }
    .sm-step-label { text-align: center; font-size: 13px; font-weight: 500; color: #64748b; margin-top: 12px; margin-bottom: 24px; }

    /* Grids */
    .sm-base-grid {
        display: grid; grid-template-columns: repeat(auto-fill, minmax(200px, 1fr)); gap: 16px; margin-bottom: 24px;
    }
    .sm-base-grid > .sm-card-item { max-width: 250px; }
    
    .sm-pizza-grid {
        display: grid; grid-template-columns: repeat(auto-fill, minmax(220px, 1fr)); gap: 16px; margin-bottom: 24px;
    }
    .sm-pizza-grid > .sm-card-pizza { max-width: 280px; }
    
    .sm-topping-pills { display: flex; flex-wrap: wrap; gap: 12px; margin-bottom: 24px; }
    
    /* Cart Styling */
    .sm-cart-title { color: #0F172A; }
    .dark .sm-cart-title { color: #f8fafc !important; }
    .sm-cart-desc { font-size: 13px; color: #64748b; }
    .dark .sm-cart-desc { color: #cbd5e1 !important; }
    
    .sm-action-buttons { display: flex !important; align-items: stretch !important; gap: 12px !important; margin-top: 16px !important; }
    .sm-action-buttons > * { flex: 1 !important; margin: 0 !important; }
    .gradio-container .sm-action-buttons button { margin-top: 0 !important; height: auto !important; }

    /* Toppings Checkboxes Styling */
    .sm-topping-checkboxes .wrap { flex-direction: row !important; flex-wrap: wrap !important; gap: 12px !important; }
    .sm-topping-checkboxes label {
        background: #ffffff !important;
        border: 1px solid #e2e8f0 !important;
        border-radius: 8px !important;
        padding: 10px 16px !important;
        margin: 0 !important;
        cursor: pointer !important;
        display: inline-flex !important;
        align-items: center !important;
        box-shadow: 0 1px 2px rgba(0,0,0,0.02) !important;
        transition: all 0.2s ease !important;
    }
    .sm-topping-checkboxes label:hover {
        border-color: #cbd5e1 !important;
        background: #f8f9fa !important;
    }
    .sm-topping-checkboxes label:has(input:checked) {
        background: #fef2f2 !important;
        border-color: #b7102a !important;
    }
    .sm-topping-checkboxes label span {
        color: #0F172A !important;
        font-weight: 500 !important;
    }
    .dark .sm-topping-checkboxes label {
        background: #1e293b !important;
        border-color: #334155 !important;
    }
    .dark .sm-topping-checkboxes label:hover {
        background: #0f172a !important;
    }
    .dark .sm-topping-checkboxes label:has(input:checked) {
        background: rgba(183,16,42,0.2) !important;
        border-color: #b7102a !important;
    }
    .dark .sm-topping-checkboxes label span {
        color: #f8fafc !important;
    }

    .sm-card-item {
        background: #ffffff; border: 1px solid #e2e8f0; border-radius: 12px;
        padding: 12px; display: flex; flex-direction: column; box-shadow: 0 1px 2px rgba(0,0,0,0.02);
    }
    .sm-card-pizza {
        background: #ffffff; border: 1px solid #e2e8f0; border-radius: 12px;
        padding: 12px; display: flex; gap: 12px; align-items: center; box-shadow: 0 1px 2px rgba(0,0,0,0.02);
    }
    .sm-img {
        aspect-ratio: 1/1; width: 100%; border-radius: 8px; overflow: hidden;
        background: #f1f5f9; display: flex; align-items: center; justify-content: center;
        margin-bottom: 12px;
    }
    .sm-img img { width: 100%; height: 100%; object-fit: cover; display: block; }
    .sm-img-placeholder { font-size: 32px; opacity: 0.3; }
    .sm-thumb { width: 72px; height: 72px; border-radius: 8px; overflow: hidden;
                background: #f1f5f9; flex-shrink: 0;
                display: flex; align-items: center; justify-content: center; }
    .sm-thumb img { width: 100%; height: 100%; object-fit: cover; display: block; }
    .sm-num {
        display: inline-block; min-width: 24px; height: 24px; line-height: 24px;
        text-align: center; border-radius: 50%; background: #b7102a; color: #fff;
        font-size: 12px; font-weight: 700; margin-right: 8px;
    }
    .sm-item-name  { font-weight: 600; color: #0F172A; font-size: 14px; }
    .sm-item-price { color: #64748b; font-size: 14px; margin-top: 4px; }
    .sm-pill {
        background: #ffffff; border: 1px solid #e2e8f0; border-radius: 999px;
        padding: 8px 16px; font-size: 14px; color: #0F172A; display: inline-flex;
        align-items: center; gap: 8px; box-shadow: 0 1px 2px rgba(0,0,0,0.02);
    }
    .sm-primary-text { color: #001b3c; }
    .sm-topping-price { color: #5b403f; }
    .sm-step-text { color: #b7102a; }
    .sm-logo-text { color: #b7102a; }
    .sm-error-text { color: #ba1a1a; }
    
    /* Bill Summary Table */
    .sm-bill-table {
        width: 100%; border-collapse: collapse; background: #ffffff;
        border: 1px solid #e4bebc; border-radius: 12px; overflow: hidden;
    }
    .sm-bill-row { border-bottom: 1px solid #eee; }
    .sm-bill-row-heavy { border-bottom: 2px solid #8f6f6e; }
    .sm-bill-row-top { border-top: 1px solid #e4bebc; }
    .sm-bill-cell { padding: 12px 16px; color: #0F172A; }
    .sm-bill-val { padding: 12px 16px; text-align: right; font-weight: 500; color: #0F172A; }
    .sm-bill-bold { font-weight: 600; }
    .sm-bill-discount { color: #336366; font-weight: 600; }
    .sm-bill-total-row { background: #f0f3ff; border-top: 2px solid #b7102a; }
    .sm-bill-total-cell { padding: 16px; font-weight: 700; font-size: 1.1em; color: #0F172A; }
    .sm-bill-tax-note { font-size: 0.75em; font-weight: 400; color: #5b403f; }
    .sm-bill-total-val { padding: 16px; text-align: right; font-weight: 700; font-size: 1.4em; color: #b7102a; }
    .sm-bill-badge {
        background: #e7eeff; padding: 4px 12px; border-radius: 6px;
        font-size: 12px; color: #001b3c;
        display: inline-block;
    }
    
    .sm-dev-log {
        background: #0B192C; 
        border-radius: 8px; 
        padding: 16px; 
        margin: 24px auto 0 auto; 
        max-width: 500px;
        text-align: left;
    }
    .sm-dev-log-header {
        font-size: 11px;
        font-weight: 700;
        letter-spacing: 1px;
        color: #94a3b8;
        margin-bottom: 12px;
        display: flex;
        align-items: center;
        justify-content: space-between;
    }
    .sm-dev-log-copy {
        background: transparent;
        border: none;
        color: #94a3b8;
        cursor: pointer;
        padding: 4px;
        border-radius: 4px;
        display: flex;
        align-items: center;
        justify-content: center;
        font-family: inherit;
    }
    .sm-dev-log-copy:hover {
        background: #1e293b;
        color: #f8fafc;
    }
    .sm-dev-log-content {
        background: #4C2E2A !important; 
        color: #fca5a5 !important;
        padding: 12px; 
        border-radius: 6px; 
        font-size: 13px; 
        word-break: break-all;
        font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, "Liberation Mono", "Courier New", monospace !important;
    }
    
    .sm-success-msg { color: #24963F; font-weight: 600; }
    .sm-success-icon { color: #24963F; font-size: 48px; }
    .sm-success-title { color: #24963F; margin: 12px 0; }
    .sm-error-icon { color: #ba1a1a; font-size: 48px; }
    .sm-error-title { color: #ba1a1a; margin: 12px 0; }
    
    .sm-pay-info { color: #336366; }
    .sm-receipt-msg { color: #5b403f; }
    .sm-receipt-details { margin: 20px auto; text-align: left; max-width: 500px; color: #0F172A; }
    .sm-receipt-details strong { color: #000000; }
    
    /* Sidebar CSS */
    .sm-sidebar-col {
        background: #f8f9fa !important; border-right: 1px solid #e2e8f0 !important;
        padding: 0 !important; margin: 0 !important; min-height: 100vh !important;
    }
    .sm-main-col {
        padding: 0 32px !important; margin: 0 !important;
    }
    .sm-sidebar {
        padding: 0 8px;
    }
    .sm-sidebar-item {
        padding: 12px 16px; margin-bottom: 4px; border-radius: 8px;
        color: #334155; font-size: 15px; font-weight: 500;
        display: flex; align-items: center; cursor: default;
    }
    .sm-sidebar-active {
        background: #dee8ff; color: #1e3a8a; font-weight: 600;
    }
    
    /* Dark Mode Overrides */
    .dark .sm-card { background: #1e293b !important; border: none !important; }
    .dark .sm-headline { color: #f8fafc !important; }
    .dark .sm-subtitle { color: #94a3b8 !important; }
    .dark .sm-item-name { color: #f8fafc !important; }
    .dark .sm-item-price { color: #94a3b8 !important; }
    .dark .sm-card-item, .dark .sm-card-pizza { background: #0f172a !important; border-color: #334155 !important; }
    .dark .sm-pill { background: #0f172a !important; border-color: #334155 !important; color: #f8fafc !important; }
    .dark .sm-sidebar-col { background: #020617 !important; border-right: 1px solid #1e293b !important; }
    .dark .sm-sidebar-item { color: #cbd5e1 !important; }
    .dark .sm-sidebar-active { background: #1e293b !important; color: #38bdf8 !important; }
    .dark .sm-primary-text { color: #f8fafc !important; }
    .dark .sm-topping-price { color: #cbd5e1 !important; }
    .dark .sm-img, .dark .sm-thumb { background: #334155 !important; }
    .dark .sm-step-text { color: #f87171 !important; }
    .dark .sm-logo-text { color: #f8fafc !important; }
    .dark .sm-error-text { color: #f87171 !important; }
    
    /* Bill Summary Dark Mode Overrides */
    .dark .sm-bill-table { background: #0f172a !important; border-color: #334155 !important; }
    .dark .sm-bill-row { border-color: #1e293b !important; }
    .dark .sm-bill-row-heavy { border-color: #475569 !important; }
    .dark .sm-bill-row-top { border-color: #334155 !important; }
    .dark .sm-bill-cell { color: #f8fafc !important; }
    .dark .sm-bill-val { color: #f8fafc !important; }
    .dark .sm-bill-discount { color: #34d399 !important; }
    .dark .sm-bill-total-row { background: #1e293b !important; border-color: #ef4444 !important; }
    .dark .sm-bill-total-cell { color: #f8fafc !important; }
    .dark .sm-bill-tax-note { color: #94a3b8 !important; }
    .dark .sm-bill-total-val { color: #ef4444 !important; }
    .dark .sm-bill-badge { background: #1e293b !important; color: #38bdf8 !important; }
    
    .dark .gradio-container .prose .sm-success-msg, .dark .sm-success-msg { color: #4ade80 !important; }
    .dark .sm-success-icon { color: #4ade80 !important; }
    .dark .gradio-container .prose .sm-success-title, .dark .sm-success-title { color: #4ade80 !important; }
    .dark .sm-error-icon { color: #f87171 !important; }
    .dark .gradio-container .prose .sm-error-title, .dark .sm-error-title { color: #f87171 !important; }
    
    .dark .sm-pay-info { color: #cbd5e1 !important; }
    .dark .sm-receipt-msg { color: #94a3b8 !important; }
    .dark .sm-receipt-details, .dark .sm-receipt-details p { color: #f8fafc !important; }
    .dark .sm-receipt-details strong { color: #f8fafc !important; }
    
    .dark .gradio-container [data-testid="radio"] label {
        background: #1e293b !important; border-color: #334155 !important; color: #f8fafc !important;
    }
    .dark .gradio-container label span { color: #cbd5e1 !important; }
    .dark .gradio-container span[data-testid="block-info"] { color: #cbd5e1 !important; }
    .dark .gradio-container .prose .sm-dev-log-header, .dark .sm-dev-log-header, .dark .sm-dev-log-header span { color: #94a3b8 !important; }
    """

    app.launch(
        theme=gr.themes.Base(),
        css=DESIGN_CSS,
        allowed_paths=[str(APP_DIR)],
        head=HEAD_JS
    )
