var stdin_buf = [];

self.addEventListener('message', function(e) {
  e.data.split("").forEach(function(ch) {
      stdin_buf.push(ch.charCodeAt(0));
  });
}, false);

var Module = {
  preRun: [function() {
    FS.init(
      function() {
        if (stdin_buf.length === 0) {
          return null;
        }
        return stdin_buf.shift();
      },
      function(ch) {
        self.postMessage({fd: "stdout", ch: ch});
      },
      function(ch) {
        self.postMessage({fd: "stderr", ch: ch});
      });
  }],
  arguments: ["xv6.img"]
};

importScripts('sim.js');
