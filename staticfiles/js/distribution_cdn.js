document.addEventListener("DOMContentLoaded", function () {
    const config = window.DIST_CDN_CONFIG || {};
    const i18n = window.DIST_CDN_I18N || {};

    const fileInput = document.getElementById("id_file");
    const displaySpan = document.getElementById("file-chosen");
    const form = document.getElementById("distribution-form");
    const tokenInput = document.querySelector(
        'input[name="cdn_confirm_token"]',
    );

    if (form) {
        form.addEventListener("submit", async function (e) {
            if (fileInput && fileInput.files && fileInput.files.length > 0) {
                e.preventDefault();

                const submitBtn = form.querySelector(
                    '[type="submit"], .action_button',
                );
                const originalText = submitBtn
                    ? submitBtn.textContent || submitBtn.value
                    : i18n.saveBtn;

                if (submitBtn) {
                    submitBtn.disabled = true;
                    submitBtn.textContent = i18n.uploading || "Загрузка...";
                }

                try {
                    // token by django
                    const tokenUrl = new URL(
                        config.getTokenUrl,
                        window.location.origin,
                    );
                    tokenUrl.searchParams.append("app_id", config.appId);

                    const tokenRes = await fetch(tokenUrl, {
                        credentials: "include",
                    });
                    if (!tokenRes.ok)
                        throw new Error("Django error: " + tokenRes.status);

                    const djangoJson = await tokenRes.json();
                    const uploadToken = djangoJson.upload_token;

                    // send to lunaspire-cdn
                    const fd = new FormData();
                    fd.append("token", uploadToken);
                    fd.append("file", fileInput.files[0]);

                    const cdnRes = await fetch(config.cdnUploadUrl, {
                        method: "POST",
                        body: fd,
                        mode: "cors",
                    });

                    if (!cdnRes.ok) {
                        const errorBody = await cdnRes.text();
                        throw new Error(
                            `CDN Rejected: ${cdnRes.status} - ${errorBody}`,
                        );
                    }

                    const cdnJson = await cdnRes.json();

                    if (!cdnJson.confirm_token) {
                        throw new Error("CDN did not return confirm_token");
                    }

                    if (tokenInput) tokenInput.value = cdnJson.confirm_token;
                    fileInput.value = "";

                    HTMLFormElement.prototype.submit.call(form);
                } catch (err) {
                    alert("Error: " + err.message);
                    if (submitBtn) {
                        submitBtn.disabled = false;
                        submitBtn.textContent = originalText;
                    }
                }
            }
        });
    }
});
