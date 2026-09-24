document.addEventListener("DOMContentLoaded", () => {

    // ==========================================
    // SIDEBAR
    // ==========================================
    const menuToggle = document.getElementById("menuToggle");
    const sidebar = document.getElementById("sidebar");
    const overlay = document.getElementById("overlay");

    function toggleSidebar() {
        const isOpen = sidebar.classList.toggle("show");
        overlay.classList.toggle("show");
        menuToggle.classList.toggle("active");
        menuToggle.setAttribute("aria-expanded", isOpen);
    }

    function closeSidebar() {
        sidebar.classList.remove("show");
        overlay.classList.remove("show");
        menuToggle.classList.remove("active");
        menuToggle.setAttribute("aria-expanded", "false");
    }

    menuToggle?.addEventListener("click", toggleSidebar);
    overlay?.addEventListener("click", closeSidebar);
    sidebar?.querySelectorAll("a").forEach(a =>
        a.addEventListener("click", closeSidebar)
    );

    // ==========================================
    // PROFILE DROPDOWN
    // ==========================================
    const btn = document.getElementById("profileBtn");
    const menu = document.getElementById("profileMenu");

    btn?.addEventListener("click", (e) => {
        e.stopPropagation();
        menu.classList.toggle("show");
    });

    document.addEventListener("click", () =>
        menu?.classList.remove("show")
    );

    // ==========================================
    // FLASH AUTO-DISMISS
    // ==========================================
    const flashes =
        document.querySelectorAll(".flash-message");

    flashes.forEach((flash) => {

        const removeFlash = () => {

            flash.style.animation =
                "fadeOut 0.4s ease forwards";

            setTimeout(() => {
                flash.remove();
            }, 400);
        };

        // Auto remove after 4s
        setTimeout(removeFlash, 4000);

        // Manual close
        flash.querySelector(".flash-close")
            ?.addEventListener("click", removeFlash);
    });

    // ==========================================
    // FILTER SYSTEM (UNIFIED)
    // ==========================================
    const category = document.getElementById("categoryFilter");
    const sort = document.getElementById("priceSort");
    const search = document.getElementById("customerProductSearch");
    const branch = document.getElementById("branchFilter");

    const fulfillmentInputs =
        document.querySelectorAll(
            'input[name="fulfillment"]'
        );

    function applyFilters() {

        const url =
            new URL(window.location.href);

        // category
        if (category) {
            url.searchParams.set(
                "category",
                category.value
            );
        }

        // sort
        if (sort) {
            url.searchParams.set(
                "sort",
                sort.value
            );
        }

        // search
        if (search) {
            url.searchParams.set(
                "search",
                search.value.trim()
            );
        }

        // branch
        if (branch) {
            url.searchParams.set(
                "branch_id",
                branch.value
            );
        }

        // fulfillment
        fulfillmentInputs.forEach(input => {
            if (input.checked) {
                url.searchParams.set(
                    "fulfillment",
                    input.value
                );
            }
        });

        // reset pagination
        url.searchParams.set("page", 1);

        // redirect
        window.location.href =
            url.toString();
    }

    // ==========================================
    // KEEP UI SYNCED WITH URL
    // ==========================================
    const params =
        new URLSearchParams(window.location.search);

    // category
    if (category) {
        category.value =
            params.get("category") || "all";
    }

    // sort
    if (sort) {
        sort.value =
            params.get("sort") || "default";
    }

    // search
    if (search) {
        search.value =
            params.get("search") || "";
    }

    // branch
    if (branch && params.get("branch_id")) {
        branch.value =
            params.get("branch_id");
    }

    // fulfillment
    const fulfillment =
        params.get("fulfillment") || "delivery";

    fulfillmentInputs.forEach(input => {
        input.checked =
            input.value === fulfillment;
    });

    // ==========================================
    // EVENTS
    // ==========================================
    category?.addEventListener(
        "change",
        applyFilters
    );

    sort?.addEventListener(
        "change",
        applyFilters
    );

    branch?.addEventListener(
        "change",
        applyFilters
    );

    // pickup/delivery toggle
    fulfillmentInputs.forEach(input => {
        input.addEventListener(
            "change",
            applyFilters
        );
    });

    // search enter
    search?.addEventListener("keydown", (e) => {

        if (e.key === "Enter") {
            e.preventDefault();
            applyFilters();
        }

    });

});