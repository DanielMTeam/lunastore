import _asyncToGenerator from "@babel/runtime/helpers/asyncToGenerator";
import _regeneratorRuntime from "@babel/runtime/regenerator";
document.addEventListener("DOMContentLoaded", function () {
  var form = document.getElementById("app-upload-form") || document.getElementById("application_form");
  if (!form) return;
  var config = window.cdn_config || window.CDN_CONFIG || {
    uploadUrl: "https://spire.lunastore.app/cdn/upload",
    tokenBaseUrl: "https://api.lunastore.app/method/user/getPubUploadToken/"
  };
  var i18n = window.luna_i18n || window.LUNA_I18N || {
    uploading: "Загрузка...",
    error: "Ошибка: ",
    tokenError: "Ошибка токена",
    fileError: "Ошибка файла"
  };
  var submitBtn = form.querySelector('[name="_save"]') || form.querySelector('[type="submit"]');
  form.addEventListener("submit", /*#__PURE__*/function () {
    var _ref = _asyncToGenerator(/*#__PURE__*/_regeneratorRuntime.mark(function _callee2(e) {
      var iconInput, screenshotsInput, hasIcon, hasScreenshots, uploadFile, tasks, iconIdx, scrStartIdx, results, cdnIconField, cdnScreenshotsField, _t;
      return _regeneratorRuntime.wrap(function (_context2) {
        while (1) switch (_context2.prev = _context2.next) {
          case 0:
            iconInput = document.getElementById("inp_icon");
            screenshotsInput = document.getElementById("inp_scr");
            hasIcon = iconInput && iconInput.files && iconInput.files[0];
            hasScreenshots = screenshotsInput && screenshotsInput.files && screenshotsInput.files.length > 0;
            if (!(!hasIcon && !hasScreenshots)) {
              _context2.next = 1;
              break;
            }
            return _context2.abrupt("return");
          case 1:
            e.preventDefault();
            if (submitBtn) submitBtn.disabled = true;
            _context2.prev = 2;
            uploadFile = /*#__PURE__*/function () {
              var _ref2 = _asyncToGenerator(/*#__PURE__*/_regeneratorRuntime.mark(function _callee(file, targetContext) {
                var baseUrl, tokenUrl, tokenRes, _yield$tokenRes$json, upload_token, fd, finalUrl, res, errMsg, data;
                return _regeneratorRuntime.wrap(function (_context) {
                  while (1) switch (_context.prev = _context.next) {
                    case 0:
                      // get personal token for file
                      baseUrl = config.tokenBaseUrl || config.tokenUrl;
                      tokenUrl = "".concat(baseUrl, "?target=").concat(targetContext);
                      _context.next = 1;
                      return fetch(tokenUrl, {
                        credentials: "include"
                      });
                    case 1:
                      tokenRes = _context.sent;
                      if (tokenRes.ok) {
                        _context.next = 2;
                        break;
                      }
                      throw new Error("".concat(i18n.tokenError, " (").concat(targetContext, ")"));
                    case 2:
                      _context.next = 3;
                      return tokenRes.json();
                    case 3:
                      _yield$tokenRes$json = _context.sent;
                      upload_token = _yield$tokenRes$json.upload_token;
                      // send file with unique token
                      fd = new FormData();
                      finalUrl = new URL(config.uploadUrl);
                      finalUrl.searchParams.append("token", upload_token);
                      fd.append("file", file);
                      fd.append("mime_type", file.type);
                      _context.next = 4;
                      return fetch(finalUrl.toString(), {
                        method: "POST",
                        body: fd
                      });
                    case 4:
                      res = _context.sent;
                      if (!(res.status !== 202 && !res.ok)) {
                        _context.next = 5;
                        break;
                      }
                      errMsg = i18n.fileError;
                      if (res.status === 415) errMsg = "Недопустимый формат файла (415).";
                      if (res.status === 409) errMsg = "Токен уже использован (409).";
                      throw new Error(errMsg);
                    case 5:
                      _context.next = 6;
                      return res.json();
                    case 6:
                      data = _context.sent;
                      return _context.abrupt("return", data.filepath || "");
                    case 7:
                    case "end":
                      return _context.stop();
                  }
                }, _callee);
              }));
              return function uploadFile(_x2, _x3) {
                return _ref2.apply(this, arguments);
              };
            }();
            tasks = [];
            iconIdx = -1; // send app icons
            if (hasIcon) {
              iconIdx = tasks.length;
              tasks.push(uploadFile(iconInput.files[0], "icon"));
            }
            scrStartIdx = tasks.length; // send screenshots
            if (hasScreenshots) {
              Array.from(screenshotsInput.files).forEach(function (f) {
                return tasks.push(uploadFile(f, "screenshot"));
              });
            }

            // waiting for result
            _context2.next = 3;
            return Promise.all(tasks);
          case 3:
            results = _context2.sent;
            cdnIconField = form.querySelector('input[name="cdn_icon_path"]');
            cdnScreenshotsField = form.querySelector('input[name="cdn_screenshots_data"]');
            if (iconIdx !== -1 && cdnIconField) cdnIconField.value = results[iconIdx];
            if (hasScreenshots && cdnScreenshotsField) {
              cdnScreenshotsField.value = JSON.stringify(results.slice(scrStartIdx));
            }
            HTMLFormElement.prototype.submit.call(form);
            _context2.next = 5;
            break;
          case 4:
            _context2.prev = 4;
            _t = _context2["catch"](2);
            alert(i18n.error + _t.message);
            if (submitBtn) submitBtn.disabled = false;
          case 5:
          case "end":
            return _context2.stop();
        }
      }, _callee2, null, [[2, 4]]);
    }));
    return function (_x) {
      return _ref.apply(this, arguments);
    };
  }());
});