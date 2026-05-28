import _asyncToGenerator from "@babel/runtime/helpers/asyncToGenerator";
import _regeneratorRuntime from "@babel/runtime/regenerator";
document.addEventListener("DOMContentLoaded", function () {
  var config = window.CDN_CONFIG;
  var avatarForm = document.getElementById("avatar-form");
  var fileInput = document.getElementById("avatar-file");
  var submitBtn = document.getElementById("avatar-submit-btn");
  var confirmTokenInput = document.querySelector('input[name="confirm_token"]');
  var filepathInput = document.querySelector('input[name="filepath"]');
  avatarForm.addEventListener("submit", /*#__PURE__*/function () {
    var _ref = _asyncToGenerator(/*#__PURE__*/_regeneratorRuntime.mark(function _callee(e) {
      var file, originalBtnText, tokenUrl, tokenResponse, tokenData, uploadToken, cdnFormData, uploadUrl, cdnResponse, cdnResult, targetPathInput, _t;
      return _regeneratorRuntime.wrap(function (_context) {
        while (1) switch (_context.prev = _context.next) {
          case 0:
            e.preventDefault();
            file = fileInput.files[0];
            if (file) {
              _context.next = 1;
              break;
            }
            alert(config.i18n.selectFile);
            return _context.abrupt("return");
          case 1:
            originalBtnText = submitBtn.innerText;
            submitBtn.innerText = config.i18n.uploading;
            submitBtn.disabled = true;
            _context.prev = 2;
            tokenUrl = new URL(config.apiTokenUrl);
            tokenUrl.searchParams.append("target", "avatar");
            _context.next = 3;
            return fetch(tokenUrl.toString(), {
              method: "GET",
              credentials: "include",
              headers: {
                Accept: "application/json"
              }
            });
          case 3:
            tokenResponse = _context.sent;
            if (tokenResponse.ok) {
              _context.next = 4;
              break;
            }
            throw new Error(config.i18n.errToken);
          case 4:
            _context.next = 5;
            return tokenResponse.json();
          case 5:
            tokenData = _context.sent;
            uploadToken = tokenData.upload_token;
            cdnFormData = new FormData();
            uploadUrl = new URL(config.cdnUploadUrl);
            uploadUrl.searchParams.append("token", uploadToken);
            cdnFormData.append("file", file);
            cdnFormData.append("mime_type", file.type);
            _context.next = 6;
            return fetch(uploadUrl.toString(), {
              method: "POST",
              body: cdnFormData
            });
          case 6:
            cdnResponse = _context.sent;
            if (!(cdnResponse.status !== 202 && !cdnResponse.ok)) {
              _context.next = 10;
              break;
            }
            if (!(cdnResponse.status === 415)) {
              _context.next = 7;
              break;
            }
            throw new Error("Файл отклонен: несоответствие типа (415). Пожалуйста, обратитесь к администратору.");
          case 7:
            if (!(cdnResponse.status === 409)) {
              _context.next = 8;
              break;
            }
            throw new Error("Ошибка: Токен уже был использован (409). Пожалуйста, обновите страницу и попробуйте снова.");
          case 8:
            if (!(cdnResponse.status === 400)) {
              _context.next = 9;
              break;
            }
            throw new Error("Неверный запрос: отсутствует mime_type (400). Пожалуйста, обратитесь к администратору.");
          case 9:
            throw new Error(config.i18n.errCdn);
          case 10:
            _context.next = 11;
            return cdnResponse.json();
          case 11:
            cdnResult = _context.sent;
            if (confirmTokenInput) {
              confirmTokenInput.value = cdnResult.confirm_token;
            }
            targetPathInput = document.querySelector('input[name="avatar_path"]') || document.querySelector('input[name="filepath"]');
            if (targetPathInput && cdnResult.filepath) {
              targetPathInput.value = cdnResult.filepath;
            }
            HTMLFormElement.prototype.submit.call(avatarForm);
            _context.next = 13;
            break;
          case 12:
            _context.prev = 12;
            _t = _context["catch"](2);
            console.error(_t);
            alert("".concat(config.i18n.errPrefix || "Ошибка:", " ").concat(_t.message));
            submitBtn.innerText = originalBtnText;
            submitBtn.disabled = false;
          case 13:
          case "end":
            return _context.stop();
        }
      }, _callee, null, [[2, 12]]);
    }));
    return function (_x) {
      return _ref.apply(this, arguments);
    };
  }());
});