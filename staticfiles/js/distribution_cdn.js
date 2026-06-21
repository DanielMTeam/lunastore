function _regenerator() {
  /*! regenerator-runtime -- Copyright (c) 2014-present, Facebook, Inc. -- license (MIT): https://github.com/babel/babel/blob/main/packages/babel-helpers/LICENSE */var e,
    t,
    r = "function" == typeof Symbol ? Symbol : {},
    n = r.iterator || "@@iterator",
    o = r.toStringTag || "@@toStringTag";
  function i(r, n, o, i) {
    var c = n && n.prototype instanceof Generator ? n : Generator,
      u = Object.create(c.prototype);
    return _regeneratorDefine2(u, "_invoke", function (r, n, o) {
      var i,
        c,
        u,
        f = 0,
        p = o || [],
        y = !1,
        G = {
          p: 0,
          n: 0,
          v: e,
          a: d,
          f: d.bind(e, 4),
          d: function d(t, r) {
            return i = t, c = 0, u = e, G.n = r, a;
          }
        };
      function d(r, n) {
        for (c = r, u = n, t = 0; !y && f && !o && t < p.length; t++) {
          var o,
            i = p[t],
            d = G.p,
            l = i[2];
          r > 3 ? (o = l === n) && (u = i[(c = i[4]) ? 5 : (c = 3, 3)], i[4] = i[5] = e) : i[0] <= d && ((o = r < 2 && d < i[1]) ? (c = 0, G.v = n, G.n = i[1]) : d < l && (o = r < 3 || i[0] > n || n > l) && (i[4] = r, i[5] = n, G.n = l, c = 0));
        }
        if (o || r > 1) return a;
        throw y = !0, n;
      }
      return function (o, p, l) {
        if (f > 1) throw TypeError("Generator is already running");
        for (y && 1 === p && d(p, l), c = p, u = l; (t = c < 2 ? e : u) || !y;) {
          i || (c ? c < 3 ? (c > 1 && (G.n = -1), d(c, u)) : G.n = u : G.v = u);
          try {
            if (f = 2, i) {
              if (c || (o = "next"), t = i[o]) {
                if (!(t = t.call(i, u))) throw TypeError("iterator result is not an object");
                if (!t.done) return t;
                u = t.value, c < 2 && (c = 0);
              } else 1 === c && (t = i["return"]) && t.call(i), c < 2 && (u = TypeError("The iterator does not provide a '" + o + "' method"), c = 1);
              i = e;
            } else if ((t = (y = G.n < 0) ? u : r.call(n, G)) !== a) break;
          } catch (t) {
            i = e, c = 1, u = t;
          } finally {
            f = 1;
          }
        }
        return {
          value: t,
          done: y
        };
      };
    }(r, o, i), !0), u;
  }
  var a = {};
  function Generator() {}
  function GeneratorFunction() {}
  function GeneratorFunctionPrototype() {}
  t = Object.getPrototypeOf;
  var c = [][n] ? t(t([][n]())) : (_regeneratorDefine2(t = {}, n, function () {
      return this;
    }), t),
    u = GeneratorFunctionPrototype.prototype = Generator.prototype = Object.create(c);
  function f(e) {
    return Object.setPrototypeOf ? Object.setPrototypeOf(e, GeneratorFunctionPrototype) : (e.__proto__ = GeneratorFunctionPrototype, _regeneratorDefine2(e, o, "GeneratorFunction")), e.prototype = Object.create(u), e;
  }
  return GeneratorFunction.prototype = GeneratorFunctionPrototype, _regeneratorDefine2(u, "constructor", GeneratorFunctionPrototype), _regeneratorDefine2(GeneratorFunctionPrototype, "constructor", GeneratorFunction), GeneratorFunction.displayName = "GeneratorFunction", _regeneratorDefine2(GeneratorFunctionPrototype, o, "GeneratorFunction"), _regeneratorDefine2(u), _regeneratorDefine2(u, o, "Generator"), _regeneratorDefine2(u, n, function () {
    return this;
  }), _regeneratorDefine2(u, "toString", function () {
    return "[object Generator]";
  }), (_regenerator = function _regenerator() {
    return {
      w: i,
      m: f
    };
  })();
}
function _regeneratorDefine2(e, r, n, t) {
  var i = Object.defineProperty;
  try {
    i({}, "", {});
  } catch (e) {
    i = 0;
  }
  _regeneratorDefine2 = function _regeneratorDefine(e, r, n, t) {
    function o(r, n) {
      _regeneratorDefine2(e, r, function (e) {
        return this._invoke(r, n, e);
      });
    }
    r ? i ? i(e, r, {
      value: n,
      enumerable: !t,
      configurable: !t,
      writable: !t
    }) : e[r] = n : (o("next", 0), o("throw", 1), o("return", 2));
  }, _regeneratorDefine2(e, r, n, t);
}
function asyncGeneratorStep(n, t, e, r, o, a, c) {
  try {
    var i = n[a](c),
      u = i.value;
  } catch (n) {
    return void e(n);
  }
  i.done ? t(u) : Promise.resolve(u).then(r, o);
}
function _asyncToGenerator(n) {
  return function () {
    var t = this,
      e = arguments;
    return new Promise(function (r, o) {
      var a = n.apply(t, e);
      function _next(n) {
        asyncGeneratorStep(a, r, o, _next, _throw, "next", n);
      }
      function _throw(n) {
        asyncGeneratorStep(a, r, o, _next, _throw, "throw", n);
      }
      _next(void 0);
    });
  };
}
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
      var _ref = _asyncToGenerator(/*#__PURE__*/_regenerator().m(function _callee(e) {
        var submitBtn, originalText, tokenUrl, tokenRes, djangoJson, uploadToken, file, uploadUrl, fd, cdnJson, _t;
        return _regenerator().w(function (_context) {
          while (1) switch (_context.p = _context.n) {
            case 0:
              if (!(fileInput && fileInput.files && fileInput.files.length > 0)) {
                _context.n = 8;
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
              _context.p = 1;
              tokenUrl = new URL(config.getTokenUrl, window.location.origin);
              tokenUrl.searchParams.append("app_id", config.appId);
              _context.n = 2;
              return fetch(tokenUrl, {
                credentials: "include"
              });
            case 2:
              tokenRes = _context.v;
              if (tokenRes.ok) {
                _context.n = 3;
                break;
              }
              throw new Error("Django error: " + tokenRes.status);
            case 3:
              _context.n = 4;
              return tokenRes.json();
            case 4:
              djangoJson = _context.v;
              uploadToken = djangoJson.upload_token;
              file = fileInput.files[0];
              uploadUrl = new URL(config.cdnUploadUrl);
              uploadUrl.searchParams.append("token", uploadToken);
              fd = new FormData();
              fd.append("file", file);
              fd.append("mime_type", file.type);
              _context.n = 5;
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
              cdnJson = _context.v;
              if (cdnJson.confirm_token) {
                _context.n = 6;
                break;
              }
              throw new Error("CDN did not return confirm_token");
            case 6:
              if (tokenInput) tokenInput.value = cdnJson.confirm_token;
              fileInput.value = "";
              HTMLFormElement.prototype.submit.call(form);
              _context.n = 8;
              break;
            case 7:
              _context.p = 7;
              _t = _context.v;
              alert("Error: " + _t.message);
              if (submitBtn) {
                submitBtn.disabled = false;
                submitBtn.textContent = originalText;
              }
              if (progressContainer) progressContainer.style.display = "none";
            case 8:
              return _context.a(2);
          }
        }, _callee, null, [[1, 7]]);
      }));
      return function (_x) {
        return _ref.apply(this, arguments);
      };
    }());
  }
});