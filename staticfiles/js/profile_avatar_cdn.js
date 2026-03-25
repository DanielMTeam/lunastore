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

        const originalBtnText = submitBtn.innerText;
        submitBtn.innerText = config.i18n.uploading;
        submitBtn.disabled = true;

        try {
            const tokenResponse = await fetch(config.apiTokenUrl, {
                method: "GET",
                credentials: "include",
                headers: { Accept: "application/json" },
            });
            if (!tokenResponse.ok) throw new Error(config.i18n.errToken);

            const tokenData = await tokenResponse.json();
            const uploadToken = tokenData.upload_token;

            const cdnFormData = new FormData();
            const uploadUrl = new URL(config.cdnUploadUrl);
            uploadUrl.searchParams.append("token", uploadToken);
            cdnFormData.append("file", file);
            cdnFormData.append("mime_type", file.type);

            const cdnResponse = await fetch(uploadUrl.toString(), {
                method: "POST",
                body: cdnFormData,
            });

            if (cdnResponse.status !== 202 && !cdnResponse.ok) {
                if (cdnResponse.status === 415)
                    throw new Error(
                        "Файл отклонен: несоответствие типа (415). Пожалуйста, обратитесь к администратору.",
                    );
                if (cdnResponse.status === 409)
                    throw new Error(
                        "Ошибка: Токен уже был использован (409). Пожалуйста, обновите страницу и попробуйте снова.",
                    );
                if (cdnResponse.status === 400)
                    throw new Error(
                        "Неверный запрос: отсутствует mime_type (400). Пожалуйста, обратитесь к администратору.",
                    );
                throw new Error(config.i18n.errCdn);
            }

            const cdnResult = await cdnResponse.json();

            if (confirmTokenInput) {
                confirmTokenInput.value = cdnResult.confirm_token;
            }

            const targetPathInput =
                document.querySelector('input[name="avatar_path"]') ||
                document.querySelector('input[name="filepath"]');

            if (targetPathInput && cdnResult.filepath) {
                targetPathInput.value = cdnResult.filepath;
            }

            HTMLFormElement.prototype.submit.call(avatarForm);
        } catch (error) {
            console.error(error);
            alert(`${config.i18n.errPrefix || "Ошибка:"} ${error.message}`);
            submitBtn.innerText = originalBtnText;
            submitBtn.disabled = false;
        }
    });
});
