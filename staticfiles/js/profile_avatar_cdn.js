document.addEventListener("DOMContentLoaded", function () {
    const config = window.CDN_CONFIG;

    const avatarForm = document.getElementById("avatar-form");
    const fileInput = document.getElementById("avatar-file");
    const submitBtn = document.getElementById("avatar-submit-btn");
    const confirmTokenInput = document.querySelector(
        'input[name="confirm_token"]',
    );
    const filepathInput = document.querySelector('input[name="filepath"]');

    avatarForm.addEventListener("submit", async function (e) {
        e.preventDefault();

        const file = fileInput.files[0];
        if (!file) {
            alert(config.i18n.selectFile);
            return;
        }

        const allowedExtensions = ["png", "jpg", "jpeg", "webp", "gif"];
        const fileExtension = file.name.split(".").pop().toLowerCase();
        const isImage = file.type.startsWith("image/");

        if (!allowedExtensions.includes(fileExtension) || !isImage) {
            alert(
                "Ошибка: Можно загружать только изображения (PNG, JPG, WEBP, GIF).",
            );
            fileInput.value = "";
            return;
        }

        const originalBtnText = submitBtn.innerText;
        submitBtn.innerText = config.i18n.uploading;
        submitBtn.disabled = true;

        try {
            const tokenResponse = await fetch(config.apiTokenUrl, {
                method: "GET",
                credentials: "include",
                headers: {
                    Accept: "application/json",
                },
            });
            if (!tokenResponse.ok) throw new Error(config.i18n.errToken);

            const tokenData = await tokenResponse.json();
            const uploadToken = tokenData.upload_token;

            const cdnFormData = new FormData();
            cdnFormData.append("token", uploadToken);
            cdnFormData.append("file", file);

            const cdnResponse = await fetch(config.cdnUploadUrl, {
                method: "POST",
                body: cdnFormData,
            });

            if (!cdnResponse.ok) throw new Error(config.i18n.errCdn);
            const cdnResult = await cdnResponse.json();

            confirmTokenInput.value = cdnResult.confirm_token;
            filepathInput.value = cdnResult.filepath;

            HTMLFormElement.prototype.submit.call(avatarForm);
        } catch (error) {
            console.error(error);
            alert(`${config.i18n.errPrefix} ${error.message}`);
            submitBtn.innerText = originalBtnText;
            submitBtn.disabled = false;
        }
    });
});
