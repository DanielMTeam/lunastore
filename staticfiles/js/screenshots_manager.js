function _indexOf(arr, val) {
  for (var i = 0; i < arr.length; i++) {
    if (arr[i] === val) return i;
  }
  return -1;
}
function ScreenshotManager(containerId, inputId, maxCount, existingPaths, cdnPrefix) {
  this.container = document.getElementById(containerId);
  this.fileInput = document.getElementById(inputId);
  this.maxCount = maxCount;
  this.items = [];
  this.counter = 0;
  this.cdnPrefix = cdnPrefix || "";
  if (!this.container || !this.fileInput) return;
  existingPaths = existingPaths || [];
  for (var i = 0; i < existingPaths.length; i++) {
    var path = existingPaths[i];
    var url = path.indexOf('http') === 0 ? path : this.cdnPrefix + path;
    this.counter++;
    this.items.push({
      id: this.counter,
      type: 'existing',
      path: path,
      url: url
    });
  }
  this.render();
  var self = this;
  if (this.fileInput.addEventListener) {
    this.fileInput.addEventListener('change', function (e) {
      self.handleFileSelect(e);
    }, false);
  } else if (this.fileInput.attachEvent) {
    this.fileInput.attachEvent('onchange', function () {
      var e = window.event;
      if (!e) e = window.event;
      if (e && !e.target) e.target = e.srcElement;
      self.handleFileSelect(e);
    });
  }
  window.activeScreenshotManager = this;
}
ScreenshotManager.prototype.handleFileSelect = function (e) {
  if (!e || !e.target) return;
  var files = e.target.files;

  // IE6 fallback: no File API
  if (!files) {
    return;
  }
  var newFiles = [];
  for (var i = 0; i < files.length; i++) {
    newFiles.push(files[i]);
  }
  this.fileInput.value = "";
  if (this.items.length + newFiles.length > this.maxCount) {
    alert("Maximum screenshots limit reached. Max: " + this.maxCount);
    return;
  }
  for (var i = 0; i < newFiles.length; i++) {
    var file = newFiles[i];
    var type = file.type || "";
    if (type !== 'image/jpeg' && type !== 'image/png' && type !== 'image/jpg') {
      alert("Invalid file format. Only JPEG and PNG are allowed: " + (file.name || ""));
      continue;
    }
    if (file.size > 2 * 1024 * 1024) {
      alert("File is too large (Maximum allowed size is 2MB): " + (file.name || ""));
      continue;
    }
    var reader = new FileReader();
    // Closure to capture file
    (function (mgr, f) {
      reader.onload = function (ev) {
        mgr.counter++;
        mgr.items.push({
          id: mgr.counter,
          type: 'new',
          file: f,
          dataUrl: ev.target.result
        });
        mgr.render();
      };
    })(this, file);
    reader.readAsDataURL(file);
  }
};
ScreenshotManager.prototype.removeItem = function (id) {
  var newItems = [];
  for (var i = 0; i < this.items.length; i++) {
    if (this.items[i].id !== id) {
      newItems.push(this.items[i]);
    }
  }
  this.items = newItems;
  this.render();
};
ScreenshotManager.prototype.moveItem = function (id, direction) {
  var idx = -1;
  for (var i = 0; i < this.items.length; i++) {
    if (this.items[i].id === id) {
      idx = i;
      break;
    }
  }
  if (idx < 0) return;
  if (direction === -1 && idx > 0) {
    var temp = this.items[idx];
    this.items[idx] = this.items[idx - 1];
    this.items[idx - 1] = temp;
  } else if (direction === 1 && idx < this.items.length - 1) {
    var temp = this.items[idx];
    this.items[idx] = this.items[idx + 1];
    this.items[idx + 1] = temp;
  }
  this.render();
};
ScreenshotManager.prototype.render = function () {
  this.container.innerHTML = "";

  // Inject base styles if not present
  if (!document.getElementById('scr_mgr_style')) {
    var style = document.createElement('style');
    style.id = 'scr_mgr_style';
    style.innerHTML = ".scr_mgr_item { float: left; margin: 5px 10px 5px 0; border: 1px solid #ccc; padding: 5px; background: #fff; width: 120px; } " + ".scr_mgr_item img { width: 120px; height: 90px; display: block; border: 1px solid #eee; } " + ".scr_mgr_controls { text-align: center; margin-top: 6px; font-size: 11px; } " + ".scr_mgr_controls a { text-decoration: none; padding: 0 4px; } " + ".scr_mgr_controls a.scr_mgr_del { color: #d9534f; font-weight: bold; } " + ".scr_mgr_controls span.disabled { color: #999; padding: 0 4px; } " + ".scr_mgr_clear { clear: both; height: 0; overflow: hidden; }";
    var head = document.getElementsByTagName('head')[0];
    if (head) head.appendChild(style);
  }
  if (this.items.length === 0) {
    this.container.innerHTML = '<div style="color: #999; font-size: 11px; padding: 10px;">Нет загруженных скриншотов</div>';
    return;
  }
  var wrapper = document.createElement('div');
  wrapper.style.overflow = "hidden"; // clearfix
  wrapper.style.width = "100%";
  var self = this;
  for (var i = 0; i < this.items.length; i++) {
    var item = this.items[i];
    var el = document.createElement('div');
    el.className = "scr_mgr_item";
    var imgSrc = item.type === 'existing' ? item.url : item.dataUrl;
    var a = document.createElement('a');
    a.href = imgSrc;
    a.className = 'thickbox';
    a.title = 'Скриншот ' + (i + 1);
    var img = document.createElement('img');
    img.src = imgSrc;
    a.appendChild(img);
    var controls = document.createElement('div');
    controls.className = "scr_mgr_controls";
    var createLink = function createLink(text, handler, disabled, isDel) {
      if (disabled) {
        var span = document.createElement('span');
        span.className = 'disabled';
        span.innerHTML = text;
        return span;
      } else {
        var link = document.createElement('a');
        link.href = "#";
        link.innerHTML = text;
        if (isDel) link.className = 'scr_mgr_del';
        link.onclick = function () {
          handler();
          return false;
        };
        return link;
      }
    };
    var btnLeft = createLink('&larr;', function (id) {
      return function () {
        self.moveItem(id, -1);
      };
    }(item.id), i === 0, false);
    var btnDel = createLink('X', function (id) {
      return function () {
        self.removeItem(id);
      };
    }(item.id), false, true);
    var btnRight = createLink('&rarr;', function (id) {
      return function () {
        self.moveItem(id, 1);
      };
    }(item.id), i === this.items.length - 1, false);
    controls.appendChild(btnLeft);
    controls.appendChild(document.createTextNode(' | '));
    controls.appendChild(btnDel);
    controls.appendChild(document.createTextNode(' | '));
    controls.appendChild(btnRight);
    el.appendChild(a);
    el.appendChild(controls);
    wrapper.appendChild(el);
  }
  var clearDiv = document.createElement('div');
  clearDiv.className = "scr_mgr_clear";
  wrapper.appendChild(clearDiv);
  this.container.appendChild(wrapper);
  if (typeof window.onScreenshotManagerRender === 'function') {
    window.onScreenshotManagerRender(this.items);
  }
};
ScreenshotManager.prototype.getNewFiles = function () {
  var arr = [];
  for (var i = 0; i < this.items.length; i++) {
    if (this.items[i].type === 'new') {
      arr.push(this.items[i].file);
    }
  }
  return arr;
};
ScreenshotManager.prototype.getExistingPaths = function () {
  var arr = [];
  for (var i = 0; i < this.items.length; i++) {
    if (this.items[i].type === 'existing') {
      arr.push(this.items[i].path);
    }
  }
  return arr;
};
ScreenshotManager.prototype.getOrderTemplate = function () {
  var arr = [];
  for (var i = 0; i < this.items.length; i++) {
    arr.push(this.items[i].type === 'existing' ? this.items[i].path : null);
  }
  return arr;
};