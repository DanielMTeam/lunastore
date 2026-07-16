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
  var form = document.getElementById("app-upload-form") || document.getElementById("application_form") || document.getElementById("distribution_form");
  if (!form) return;
  var config = window.cdn_config || window.CDN_CONFIG || {
    uploadUrl: "https://spire.lunastore.app/cdn/upload",
    tokenBaseUrl: "https://api.lunastore.app/method/user/getPublicUploadToken/"
  };
  var i18n = window.luna_i18n || window.LUNA_I18N || {
    uploading: "Загрузка...",
    error: "Ошибка: ",
    tokenError: "Ошибка токена",
    fileError: "Ошибка файла"
  };
  var submitBtn = form.querySelector('[name="_save"]') || form.querySelector('[type="submit"]');
  form.addEventListener("submit", /*#__PURE__*/function () {
    var _ref = _asyncToGenerator(/*#__PURE__*/_regenerator().m(function _callee2(e) {
      var iconInput, screenshotsInput, distInput, inlineDistInputs, hasIcon, hasScreenshots, hasDist, hasInlineDist, uploadFile, tasks, iconIdx, scrStartIdx, distIdx, inlineDistTasks, results, cdnIconField, cdnIconTokenField, cdnScreenshotsField, cdnScreenshotsTokenField, cdnConfirmTokenField, resultsSlice, tokens, paths, _t, mgr, newFiles;
      return _regenerator().w(function (_context2) {
        while (1) switch (_context2.p = _context2.n) {
          case 0:
            iconInput = document.querySelector('input[type="file"][name="icon_file"]');
            screenshotsInput = document.querySelector('input[type="file"][name="screenshots_files"]') || document.querySelector('input[type="file"][name="upload_screenshots"]');
            distInput = document.querySelector('input[type="file"][name="dist_file"]');
            inlineDistInputs = Array.from(document.querySelectorAll('input[type="file"][name$="-dist_file"]'));
            hasIcon = iconInput && iconInput.files && iconInput.files[0];
            mgr = window.activeScreenshotManager;
            newFiles = mgr ? mgr.getNewFiles() : screenshotsInput && screenshotsInput.files ? Array.from(screenshotsInput.files) : [];
            hasScreenshots = mgr ? true : newFiles.length > 0;
            hasDist = distInput && distInput.files && distInput.files[0];
            hasInlineDist = inlineDistInputs.some(function (inp) {
              return inp.files && inp.files.length > 0;
            });
            if (!(!hasIcon && !hasScreenshots && !hasDist && !hasInlineDist)) {
              _context2.n = 1;
              break;
            }
            return _context2.a(2);
          case 1:
            e.preventDefault();
            if (submitBtn) submitBtn.disabled = true;
            _context2.p = 2;
            uploadFile = /*#__PURE__*/function () {
              var _ref2 = _asyncToGenerator(/*#__PURE__*/_regenerator().m(function _callee(file, targetContext) {
                var tokenUrl, currentAppId, appSelect, baseUrl, tokenRes, _yield$tokenRes$json, upload_token, fd, finalUrl, res, errMsg, data;
                return _regenerator().w(function (_context) {
                  while (1) switch (_context.n) {
                    case 0:
                      if (!(targetContext === "distribution")) {
                        _context.n = 2;
                        break;
                      }
                      currentAppId = config.appId;
                      if (!currentAppId) {
                        appSelect = document.querySelector('select[name="app"]');
                        if (appSelect) {
                          currentAppId = appSelect.value;
                        }
                      }
                      if (currentAppId) {
                        _context.n = 1;
                        break;
                      }
                      throw new Error("Can't upload distribution: app not selected or not saved. Please select an app in the list.");
                    case 1:
                      tokenUrl = "".concat(config.privTokenUrl, "?target=").concat(targetContext, "&app_id=").concat(currentAppId);
                      _context.n = 3;
                      break;
                    case 2:
                      baseUrl = config.tokenBaseUrl || config.tokenUrl;
                      tokenUrl = "".concat(baseUrl, "?target=").concat(targetContext);
                    case 3:
                      _context.n = 4;
                      return fetch(tokenUrl, {
                        credentials: "include"
                      });
                    case 4:
                      tokenRes = _context.v;
                      if (tokenRes.ok) {
                        _context.n = 5;
                        break;
                      }
                      throw new Error("".concat(i18n.tokenError, " (").concat(targetContext, ")"));
                    case 5:
                      _context.n = 6;
                      return tokenRes.json();
                    case 6:
                      _yield$tokenRes$json = _context.v;
                      upload_token = _yield$tokenRes$json.upload_token;
                      // send file with unique token
                      fd = new FormData();
                      finalUrl = new URL(config.uploadUrl);
                      finalUrl.searchParams.append("token", upload_token);
                      fd.append("file", file);
                      fd.append("mime_type", file.type);
                      _context.n = 7;
                      return fetch(finalUrl.toString(), {
                        method: "POST",
                        body: fd
                      });
                    case 7:
                      res = _context.v;
                      if (!(res.status !== 202 && !res.ok)) {
                        _context.n = 8;
                        break;
                      }
                      errMsg = i18n.fileError;
                      if (res.status === 415) errMsg = "Invalid file format (415).";
                      if (res.status === 409) errMsg = "Token already used (409).";
                      throw new Error(errMsg);
                    case 8:
                      _context.n = 9;
                      return res.json();
                    case 9:
                      data = _context.v;
                      return _context.a(2, data);
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
            newFiles.forEach(function (f) {
              return tasks.push(uploadFile(f, "screenshot"));
            });

            // send dist
            distIdx = -1;
            if (hasDist) {
              distIdx = tasks.length;
              tasks.push(uploadFile(distInput.files[0], "distribution"));
            }

            // send inline dists
            inlineDistTasks = [];
            inlineDistInputs.forEach(function (input) {
              if (input.files && input.files[0]) {
                inlineDistTasks.push({
                  input: input,
                  taskIdx: tasks.length
                });
                tasks.push(uploadFile(input.files[0], "distribution"));
              }
            });

            // waiting for result
            _context2.n = 3;
            return Promise.all(tasks);
          case 3:
            results = _context2.v;
            cdnIconField = form.querySelector('input[name="cdn_icon_path"]');
            cdnIconTokenField = form.querySelector('input[name="cdn_icon_confirm_token"]');
            cdnScreenshotsField = form.querySelector('input[name="cdn_screenshots_data"]');
            cdnScreenshotsTokenField = form.querySelector('input[name="cdn_screenshots_tokens"]');
            cdnConfirmTokenField = form.querySelector('input[name="cdn_confirm_token"]');
            if (iconIdx !== -1) {
              if (cdnIconTokenField) cdnIconTokenField.value = results[iconIdx].confirm_token || "";
              if (cdnIconField) cdnIconField.value = results[iconIdx].filepath || results[iconIdx].path || "";
            }
            if (hasScreenshots || mgr) {
              resultsSlice = results.slice(scrStartIdx, scrStartIdx + newFiles.length);
              if (cdnScreenshotsTokenField) {
                tokens = resultsSlice.map(function (d) {
                  return d.confirm_token;
                }).filter(function (t) {
                  return t;
                });
                if (tokens.length > 0) cdnScreenshotsTokenField.value = JSON.stringify(tokens);
              }
              if (cdnScreenshotsField) {
                if (mgr) {
                  var orderTemplate = mgr.getOrderTemplate();
                  var newPathsIndex = 0;
                  paths = orderTemplate.map(function (item) {
                    if (item !== null) return item;
                    var res = resultsSlice[newPathsIndex++];
                    return res ? res.filepath || res.path || "" : "";
                  }).filter(function (p) {
                    return p;
                  });
                } else {
                  paths = [];
                  resultsSlice.forEach(function (res) {
                    if (res && (res.filepath || res.path)) paths.push(res.filepath || res.path);
                  });
                }
                if (!paths || paths.length === 0) {
                  cdnScreenshotsField.value = "[]";
                } else {
                  cdnScreenshotsField.value = JSON.stringify(paths);
                }
              }
            } else {
              if (cdnScreenshotsField && cdnScreenshotsField.value === "") {
                cdnScreenshotsField.value = "[]";
              }
            }
            if (distIdx !== -1 && cdnConfirmTokenField) {
              cdnConfirmTokenField.value = results[distIdx].confirm_token || "";
            }
            inlineDistTasks.forEach(function (item) {
              var prefix = item.input.name.replace('-dist_file', '');
              var inlineTokenField = form.querySelector("input[name=\"".concat(prefix, "-cdn_confirm_token\"]"));
              if (inlineTokenField) {
                inlineTokenField.value = results[item.taskIdx].confirm_token || "";
              } else {
                alert("WARNING: cdn_confirm_token field not found for " + prefix);
              }
            });
            HTMLFormElement.prototype.submit.call(form);
            _context2.n = 5;
            break;
          case 4:
            _context2.p = 4;
            _t = _context2.v;
            alert(i18n.error + _t.message);
            if (submitBtn) submitBtn.disabled = false;
          case 5:
            return _context2.a(2);
        }
      }, _callee2, null, [[2, 4]]);
    }));
    return function (_x) {
      return _ref.apply(this, arguments);
    };
  }());
});