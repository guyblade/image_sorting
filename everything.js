$().ready(function() {
  var rpc_base_path = '/rpc/';
  var cache_invalidated = false;

  function ToPromise(val) {
    return new Promise(function(resolve, reject) { resolve(val); });
  }

  var ImageList = (function() {
    var image_list_cache;
    var image_list_cache_valid = false;
    var current_request;
    var pending = false;

    var actual = function() {
      if (image_list_cache_valid && !cache_invalidated) {
        return ToPromise(image_list_cache);
      }
      cache_invalidated = false;
      if (pending) {
        return current_request;
      }
      current_request = $.xmlrpc({
        url: rpc_base_path,
        methodName: 'ImageList',
        params: [],
      }).then(function(response) {
          image_list_cache = response[0];
          image_list_cache_valid = true;
          pending = false;
          return image_list_cache;
      });
      pending = true;
      return current_request;
    }
    return actual;
  })();

  function SaveImage() {
    console.log("Trying to save the current image.");
    ImageList().then(function(image_list) {
      var page = GetCurrentPage(image_list);

      $.xmlrpc({
        url: rpc_base_path,
        methodName: 'MoveImage',
        params: [image_list[page]]
      }).then(function(response) {
        if (response[0]) {
          HashChanger(image_list[page+1])();
          WriteError("");
        } else {
          WriteError("Couldn't copy image to destination directory?");
        }
      });
    });
  }

  function gcd(a, b) {
    console.log("Getting gcd of " + a + ',' + b);
    var cnt = 0;
    while (a != b) {
      if (cnt++ > 100000) {
        return 1;
      }
      if (a > b) {
        var na = a - b;
        var nb = b;
        a = na;
        b = nb;
      } else {
        var na = a;
        var nb = b - a;
        a = na;
        b = nb;
      }
    }
    console.log("GCD is " + a);
    return a;
  }

  function WriteError(msg) {
    $("#notes").html(msg);
  }

  function DeterminePageNumber(image_list, image_name) {
    for (var i = 0; i < image_list.length - 1; i++) {
      if (image_list[i] == image_name) {// ||
          //(i > 0 && image_list[i-1] < image_name &&
          // image_name < image_list[i])) {
        return i;
      }
    }
    return 0;
  }

  function GetCurrentPage(image_list) {
    var image_name = decodeURI(window.location.hash.substr(1));
    return DeterminePageNumber(image_list, image_name);
  }

  function HashChanger(new_hash) {
    return function() {
      document.location.hash = new_hash;
    };
  }

  var KeybindManager = (function() {
    var key_map = {};
    var did_init = false;
    var rebind = function(key, action) {
      if (!did_init) {
        init();
      }
      key_map[key] = action;
    };

    var unbind = function(key) {
      delete key_map[key];
    };

    var handle = function(event) {
      console.log("Got keypress event: " + event);
      var key = event.key;
      if (!(key in key_map)) {
        console.log("Unrecognized key: [" + key + "]");
        return;
      }
      event.preventDefault();
      (key_map[key])()
    };

    var init = function() {
      did_init = true;
      console.log("Registering keypress handler");
      $(document).keydown(handle);
    };

    return {'init':init, 'rebind':rebind, 'unbind':unbind, 'handle':handle};
  })();

  function DimensionFiller(obj) {
    var ret = function() {
      console.log("Image Loaded?");
      var img = $("#main_image")[0];
      console.log(img);
      var cd = gcd(img.naturalWidth, img.naturalHeight);
      obj.append("  (" + img.naturalWidth + " x " + img.naturalHeight + ")");
      obj.append("  [" + (img.naturalWidth / cd) + ":" + (img.naturalHeight / cd) + "]");
      console.log("Wrote dimension information");
    };
    return ret;
  }

  function FillNavigation() {
    ImageList().then(function(image_list) {
      $("#controls").empty();
      var page = GetCurrentPage(image_list);
      console.log("Currently on page " + page + " of " + image_list.length);
      $("#main_image").removeAttr('src');
      $("#main_image").attr('src', 'img/' + image_list[page]);
      KeybindManager.unbind('ArrowLeft');
      KeybindManager.unbind('ArrowRight');
      if (page > 0) {
         var name = image_list[page-1];
         var prev = $("<a class='link'>Previous</a>");
         prev.click(HashChanger(name));
         KeybindManager.rebind('ArrowLeft', HashChanger(name));
         $("#controls").append(prev);
         $("#controls").append("&nbsp;&nbsp;&nbsp;");
      }
      if (page + 1 < image_list.length) {
         var name = image_list[page+1];
         var next = $("<a class='link'>Next</a>");
         next.click(HashChanger(name));
         KeybindManager.rebind('ArrowRight', HashChanger(name));
         $("#controls").append(next);
      }
      $("#controls").append("<br>" + image_list[page]);
      var dimensions = $("<span></span>");
      $("#controls").append(dimensions);
      $("#controls").append("<br>");
      $("#main_image").on('load', DimensionFiller(dimensions));
      var save = $("<a class='link save'>Save</a>");
      save.click(SaveImage);
      $("#controls").append(save);
      KeybindManager.rebind('s', SaveImage);
      console.log("Done adding navigation");
    });
  }

  function SetUp() {
    ImageList().then(function(images) { console.log(images); });
    ImageList().then(function(images) { console.log(images); });
    FillNavigation();
    window.onhashchange = FillNavigation;
  }

  SetUp();
});
