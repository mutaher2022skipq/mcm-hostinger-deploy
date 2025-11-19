document.addEventListener("DOMContentLoaded", function () {

    const classSelect = document.getElementById("feeClassSelect");
    const categorySelect = document.getElementById("feeCategorySelect");
    const datePicker = document.getElementById("feeDatePicker");

    const amountBox = document.getElementById("feeAmount");
    const tierBox = document.getElementById("feeTier");

    function fetchFeePreview() {
        if (!classSelect.value || !datePicker.value) return;

        let url = `/admissions/admin/fees/preview/?class_name=${classSelect.value}&date=${datePicker.value}&category=${categorySelect.value}`;

        fetch(url)
            .then(res => res.json())
            .then(data => {
                if (data.success) {
                    amountBox.innerText = data.amount + " PKR";
                    tierBox.innerText = data.tier;
                } else {
                    amountBox.innerText = "--";
                    tierBox.innerText = "--";
                }
            });
    }

    classSelect?.addEventListener("change", fetchFeePreview);
    categorySelect?.addEventListener("change", fetchFeePreview);
    datePicker?.addEventListener("input", fetchFeePreview);
});
