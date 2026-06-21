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
  var config = window.CDN_CONFIG;
  var avatarForm = document.getElementById("avatar-form");
  var fileInput = document.getElementById("avatar-file");
  var submitBtn = document.getElementById("avatar-submit-btn");
  var confirmTokenInput = document.querySelector('input[name="confirm_token"]');
  var filepathInput = document.querySelector('input[name="filepath"]');
  avatarForm.addEventListener("submit", /*#__PURE__*/function () {
    var _ref = _asyncToGenerator(/*#__PURE__*/_regenerator().m(function _callee(e) {
      var file, originalBtnText, tokenUrl, tokenResponse, tokenData, uploadToken, cdnFormData, uploadUrl, cdnResponse, cdnResult, targetPathInput, _t;
      return _regenerator().w(function (_context) {
        while (1) switch (_context.p = _context.n) {
          case 0:
            e.preventDefault();
            file = fileInput.files[0];
            if (file) {
              _context.n = 1;
              break;
            }
            alert(config.i18n.selectFile);
            return _context.a(2);
          case 1:
            originalBtnText = submitBtn.innerText;
            submitBtn.innerText = config.i18n.uploading;
            submitBtn.disabled = true;
            _context.p = 2;
            tokenUrl = new URL(config.apiTokenUrl);
            tokenUrl.searchParams.append("target", "avatar");
            _context.n = 3;
            return fetch(tokenUrl.toString(), {
              method: "GET",
              credentials: "include",
              headers: {
                Accept: "application/json"
              }
            });
          case 3:
            tokenResponse = _context.v;
            if (tokenResponse.ok) {
              _context.n = 4;
              break;
            }
            throw new Error(config.i18n.errToken);
          case 4:
            _context.n = 5;
            return tokenResponse.json();
          case 5:
            tokenData = _context.v;
            uploadToken = tokenData.upload_token;
            cdnFormData = new FormData();
            uploadUrl = new URL(config.cdnUploadUrl);
            uploadUrl.searchParams.append("token", uploadToken);
            cdnFormData.append("file", file);
            cdnFormData.append("mime_type", file.type);
            _context.n = 6;
            return fetch(uploadUrl.toString(), {
              method: "POST",
              body: cdnFormData
            });
          case 6:
            cdnResponse = _context.v;
            if (!(cdnResponse.status !== 202 && !cdnResponse.ok)) {
              _context.n = 10;
              break;
            }
            if (!(cdnResponse.status === 415)) {
              _context.n = 7;
              break;
            }
            throw new Error("Файл отклонен: несоответствие типа (415). Пожалуйста, обратитесь к администратору.");
          case 7:
            if (!(cdnResponse.status === 409)) {
              _context.n = 8;
              break;
            }
            throw new Error("Ошибка: Токен уже был использован (409). Пожалуйста, обновите страницу и попробуйте снова.");
          case 8:
            if (!(cdnResponse.status === 400)) {
              _context.n = 9;
              break;
            }
            throw new Error("Неверный запрос: отсутствует mime_type (400). Пожалуйста, обратитесь к администратору.");
          case 9:
            throw new Error(config.i18n.errCdn);
          case 10:
            _context.n = 11;
            return cdnResponse.json();
          case 11:
            cdnResult = _context.v;
            if (confirmTokenInput) {
              confirmTokenInput.value = cdnResult.confirm_token;
            }
            targetPathInput = document.querySelector('input[name="avatar_path"]') || document.querySelector('input[name="filepath"]');
            if (targetPathInput && cdnResult.filepath) {
              targetPathInput.value = cdnResult.filepath;
            }
            HTMLFormElement.prototype.submit.call(avatarForm);
            _context.n = 13;
            break;
          case 12:
            _context.p = 12;
            _t = _context.v;
            console.error(_t);
            alert("".concat(config.i18n.errPrefix || "Ошибка:", " ").concat(_t.message));
            submitBtn.innerText = originalBtnText;
            submitBtn.disabled = false;
          case 13:
            return _context.a(2);
        }
      }, _callee, null, [[2, 12]]);
    }));
    return function (_x) {
      return _ref.apply(this, arguments);
    };
  }());
});