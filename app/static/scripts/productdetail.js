/* =========================================
   SETOHIL STORE MAIN JS
========================================= */

document.addEventListener("DOMContentLoaded", () => {

    // =========================================
    // HELPERS
    // =========================================

    const $ = (selector, parent = document) =>
        parent.querySelector(selector);

    const $$ = (selector, parent = document) =>
        [...parent.querySelectorAll(selector)];

    const formatCurrency = (value = 0) =>
        `£${Number(value).toFixed(2)}`;

    const onlyDigits = (value = "") =>
        value.replace(/\D/g, "");

    // =========================================
    // FLASH MESSAGES
    // =========================================

    function initFlashMessages() {

        const flashes = $$(".flash-message");

        flashes.forEach(flash => {

            const removeFlash = () => flash.remove();

            setTimeout(removeFlash, 4000);

            flash.querySelector(".flash-close")
                ?.addEventListener("click", removeFlash);
        });
    }

    // =========================================
    // SIDEBAR
    // =========================================

    function initSidebar() {

        const menuBtn = $("#menuToggle");
        const sidebar = $("#sidebar");
        const overlay = $("#overlay");

        if (!menuBtn || !sidebar || !overlay) return;

        const toggleSidebar = (show) => {

            sidebar.classList.toggle("show", show);
            overlay.classList.toggle("show", show);

            menuBtn.setAttribute("aria-expanded", show);
        };

        menuBtn.addEventListener("click", () => {

            const isOpen = sidebar.classList.contains("show");

            toggleSidebar(!isOpen);
        });

        overlay.addEventListener("click", () => {
            toggleSidebar(false);
        });
    }

    // =========================================
    // PROFILE DROPDOWN
    // =========================================

    function initProfileDropdown() {

        const profileBtn = $("#profileBtn");
        const profileMenu = $("#profileMenu");

        if (!profileBtn || !profileMenu) return;

        profileBtn.addEventListener("click", (e) => {

            e.stopPropagation();

            profileMenu.classList.toggle("show");
        });

        document.addEventListener("click", () => {
            profileMenu.classList.remove("show");
        });
    }

    // =========================================
    // CHECKOUT
    // =========================================

    function initCheckout() {

        const form = $(".checkout-form");

        if (!form) return;

        const orderMethod = $("#order-method");

        const deliverySection = $("#delivery-details");
        const pickupSection = $("#pickup-details");

        const summary = $(".checkout-summary");

        if (!summary || !orderMethod) return;

        // Values from backend
        const subtotal = Number(summary.dataset.subtotal || 0);
        const deliveryFee = Number(summary.dataset.delivery || 0);

        // UI Elements
        const subtotalEl = $("#subtotal-value");
        const deliveryEl = $("#delivery-value");
        const totalEl = $("#total-value");

        // =====================================
        // UPDATE TOTALS
        // =====================================

        const updateCheckoutTotals = () => {

            const isDelivery =
                orderMethod.value === "delivery";

            // Toggle sections
            if (deliverySection) {
                deliverySection.classList.toggle(
                    "hidden",
                    !isDelivery
                );
            }

            if (pickupSection) {
                pickupSection.classList.toggle(
                    "hidden",
                    isDelivery
                );
            }

            // Pickup has NO delivery fee
            const shippingCost =
                isDelivery ? deliveryFee : 0;

            const grandTotal =
                subtotal + shippingCost;

            // Update UI
            if (subtotalEl) {
                subtotalEl.textContent =
                    formatCurrency(subtotal);
            }

            if (deliveryEl) {
                deliveryEl.textContent =
                    formatCurrency(shippingCost);
            }

            if (totalEl) {
                totalEl.textContent =
                    formatCurrency(grandTotal);
            }
        };

        // Initial render
        updateCheckoutTotals();

        // Change order type
        orderMethod.addEventListener(
            "change",
            updateCheckoutTotals
        );

        // Submit
        form.addEventListener("submit", () => {
            console.log("Checkout form submitted");
        });
    }

    // =========================================
    // CART QUANTITY
    // =========================================

    function initCartQuantity() {

        const quantityInputs =
            $$("input[data-update-url]");

        if (!quantityInputs.length) return;

        // =====================================
        // UPDATE CART API
        // =====================================

        async function updateCart(url, quantity, itemId) {

            try {

                const response = await fetch(url, {
                    method: "POST",
                    headers: {
                        "Content-Type":
                            "application/x-www-form-urlencoded"
                    },
                    body: new URLSearchParams({
                        quantity
                    })
                });

                const data = await response.json();

                if (!data.success) {
                    console.error("Cart update failed");
                    return;
                }

                // =================================
                // ITEM SUBTOTAL
                // =================================

                const itemSubtotal =
                    document.getElementById(
                        `subtotal-${itemId}`
                    );

                if (itemSubtotal) {
                    itemSubtotal.textContent =
                        formatCurrency(data.subtotal);
                }

                // =================================
                // CART SUMMARY
                // =================================

                const subtotalEl =
                    $("#cart-subtotal");

                const shippingEl =
                    $("#cart-shipping");

                const totalEl =
                    $("#cart-total");

                if (subtotalEl) {
                    subtotalEl.textContent =
                        formatCurrency(
                            data.subtotal_total
                        );
                }

                // Pickup = free shipping
                if (shippingEl) {
                    shippingEl.textContent =
                        formatCurrency(
                            data.shipping || 0
                        );
                }

                if (totalEl) {
                    totalEl.textContent =
                        formatCurrency(data.total);
                }

            } catch (error) {

                console.error(
                    "Cart update error:",
                    error
                );
            }
        }

        // =====================================
        // BUTTON EVENTS
        // =====================================

        quantityInputs.forEach(input => {

            const updateUrl =
                input.dataset.updateUrl;

            const itemId =
                input.dataset.cartItemId;

            const wrapper =
                input.closest(".qty-counter");

            if (!wrapper) return;

            const minusBtn =
                $(".minus", wrapper);

            const plusBtn =
                $(".plus", wrapper);

            // -----------------------------
            // MINUS
            // -----------------------------

            minusBtn?.addEventListener(
                "click",
                () => {

                    let quantity =
                        parseInt(input.value || "1");

                    quantity = Math.max(
                        1,
                        quantity - 1
                    );

                    input.value = quantity;

                    updateCart(
                        updateUrl,
                        quantity,
                        itemId
                    );
                }
            );

            // -----------------------------
            // PLUS
            // -----------------------------

            plusBtn?.addEventListener(
                "click",
                () => {

                    let quantity =
                        parseInt(input.value || "1");

                    quantity += 1;

                    input.value = quantity;

                    updateCart(
                        updateUrl,
                        quantity,
                        itemId
                    );
                }
            );

            // -----------------------------
            // MANUAL INPUT
            // -----------------------------

            input.addEventListener(
                "change",
                () => {

                    let quantity =
                        parseInt(input.value || "1");

                    quantity = Math.max(
                        1,
                        quantity
                    );

                    input.value = quantity;

                    updateCart(
                        updateUrl,
                        quantity,
                        itemId
                    );
                }
            );
        });
    }

    // =========================================
    // INITIALIZE ALL
    // =========================================

    initFlashMessages();

    initSidebar();

    initProfileDropdown();

    initCheckout();

    initCartQuantity();

});