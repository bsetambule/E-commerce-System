document.addEventListener(
    "DOMContentLoaded",
    () => {

        const form =
            document.getElementById(
                "checkout-form"
            );

        if (!form) {
            return;
        }

        const submitBtn =
            document.getElementById(
                "checkout-submit"
            );

        form.addEventListener(
            "submit",
            async (e) => {

                e.preventDefault();

                if (
                    form.dataset.processing
                    === "true"
                ) {
                    return;
                }

                form.dataset.processing =
                    "true";

                submitBtn.disabled = true;

                submitBtn.innerText =
                    "Processing...";

                try {

                    const formData =
                        new FormData(form);

                    const payload =
                        Object.fromEntries(
                            formData.entries()
                        );

                    const countryCode =
                        formData.get(
                            "country_code"
                        );

                    const phone =
                        formData.get("phone")
                            .replace(/\D/g, "");

                    payload.phone =
                        `${countryCode}${phone}`;

                    delete payload.country_code;

                    const response =
                        await fetch(
                            "/checkout/create",
                            {
                                method: "POST",

                                credentials:
                                    "same-origin",

                                headers: {
                                    "Content-Type":
                                        "application/json"
                                },

                                body: JSON.stringify(
                                    payload
                                )
                            }
                        );

                    const data =
                        await response.json();

                    if (!response.ok) {

                        throw new Error(
                            data.error
                            || "Checkout failed"
                        );
                    }

                    window.location.href =
                        data.checkout_url;

                } catch (err) {

                    alert(err.message);

                    form.dataset.processing =
                        "false";

                    submitBtn.disabled =
                        false;

                    submitBtn.innerText =
                        "Place Order";
                }
            }
        );
    }
);