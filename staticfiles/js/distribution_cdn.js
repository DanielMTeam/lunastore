import _asyncToGenerator from "@babel/runtime/helpers/asyncToGenerator";
import _regeneratorRuntime from "@babel/runtime/regenerator";
document.addEventListener("DOMContentLoaded", function () {
  var config = window.DIST_CDN_CONFIG || {};
  var i18n = window.DIST_CDN_I18N || {};
  var fileInput = document.getElementById("id_file");
  var form = document.getElementById("distribution-form");
  var tokenInput = document.querySelector('input[name="cdn_confirm_token"]');
  var progressContainer = document.getElementById("progress-container");
  var progressBar = document.getElementById("progress-bar-fill");
  var progressText = document.getElementById("progress-text");
  if (form) {
    form.addEventListener("submit", /*#__PURE__*/function () {
      var _ref = _asyncToGenerator(/*#__PURE__*/_regeneratorRuntime.mark(function _callee(e) {
        var submitBtn, originalText, tokenUrl, tokenRes, djangoJson, uploadToken, file, uploadUrl, fd, cdnJson, _t;
        return _regeneratorRuntime.wrap(function (_context) {
          while (1) switch (_context.prev = _context.next) {
            case 0:
              if (!(fileInput && fileInput.files && fileInput.files.length > 0)) {
                _context.next = 8;
                break;
              }
              e.preventDefault();
              submitBtn = form.querySelector('[type="submit"], .action_button');
              originalText = submitBtn ? submitBtn.textContent || submitBtn.value : i18n.saveBtn;
              if (submitBtn) {
                submitBtn.disabled = true;
                submitBtn.textContent = i18n.uploading || "Загрузка...";
              }
              if (progressContainer) {
                progressContainer.style.display = "block";
                if (progressBar) progressBar.style.width = "0%";
                if (progressText) progressText.textContent = "0%";
              }
              _context.prev = 1;
              tokenUrl = new URL(config.getTokenUrl, window.location.origin);
              tokenUrl.searchParams.append("app_id", config.appId);
              _context.next = 2;
              return fetch(tokenUrl, {
                credentials: "include"
              });
            case 2:
              tokenRes = _context.sent;
              if (tokenRes.ok) {
                _context.next = 3;
                break;
              }
              throw new Error("Django error: " + tokenRes.status);
            case 3:
              _context.next = 4;
              return tokenRes.json();
            case 4:
              djangoJson = _context.sent;
              uploadToken = djangoJson.upload_token;
              file = fileInput.files[0];
              uploadUrl = new URL(config.cdnUploadUrl);
              uploadUrl.searchParams.append("token", uploadToken);
              fd = new FormData();
              fd.append("file", file);
              fd.append("mime_type", file.type);
              _context.next = 5;
              return new Promise(function (resolve, reject) {
                var xhr = new XMLHttpRequest();
                xhr.open("POST", uploadUrl.toString());
                xhr.upload.addEventListener("progress", function (event) {
                  if (event.lengthComputable) {
                    var percentComplete = Math.round(event.loaded / event.total * 100);
                    if (progressBar) progressBar.style.width = "".concat(percentComplete, "%");
                    if (progressText) progressText.textContent = "".concat(percentComplete, "%");
                  }
                });
                xhr.onload = function () {
                  if (xhr.status === 202 || xhr.status >= 200 && xhr.status < 300) {
                    try {
                      var responseJson = JSON.parse(xhr.responseText);
                      resolve(responseJson);
                    } catch (e) {
                      reject(new Error("Некорректынй JSON от LunaSpire. Пожалуйста, обратитесь к администратору."));
                    }
                  } else {
                    var errorMsg = "\u041E\u0448\u0438\u0431\u043A\u0430 LunaSpire (".concat(xhr.status, "): ").concat(xhr.responseText);
                    if (xhr.status === 415) errorMsg = "Ошибка: недопустимый тип файла (415 HTTP error). Пожалуйста, обратитесь к администратору.";
                    if (xhr.status === 409) errorMsg = "Ошибка: этот токен загрузки уже использован (409 HTTP error). Пожалуйста, обновите страницу.";
                    reject(new Error(errorMsg));
                  }
                };
                xhr.onerror = function () {
                  reject(new Error("Ошибка сети. Пожалуйста, проверьте подключение к интернету."));
                };
                xhr.send(fd);
              });
            case 5:
              cdnJson = _context.sent;
              if (cdnJson.confirm_token) {
                _context.next = 6;
                break;
              }
              throw new Error("CDN did not return confirm_token");
            case 6:
              if (tokenInput) tokenInput.value = cdnJson.confirm_token;
              fileInput.value = "";
              HTMLFormElement.prototype.submit.call(form);
              _context.next = 8;
              break;
            case 7:
              _context.prev = 7;
              _t = _context["catch"](1);
              alert("Error: " + _t.message);
              if (submitBtn) {
                submitBtn.disabled = false;
                submitBtn.textContent = originalText;
              }
              if (progressContainer) progressContainer.style.display = "none";
            case 8:
            case "end":
              return _context.stop();
          }
        }, _callee, null, [[1, 7]]);
      }));
      return function (_x) {
        return _ref.apply(this, arguments);
      };
    }());
  }
});