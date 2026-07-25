'use strict';

/**
 * Central configuration for the White Hat Lab backend.
 *
 * SAFETY-CRITICAL DEFAULT:
 * -----------------------------------------------------------------------------
 * `HOST` defaults to 127.0.0.1 (the loopback interface). This is the single most
 * important safety control in the whole project. Because the training server
 * hosts *intentionally* vulnerable endpoints, it must NEVER be reachable from
 * another machine on the network or the internet.
 *
 * Binding to 127.0.0.1 means the operating system only accepts connections that
 * originate from this same computer. Even if someone knows your IP address, the
 * kernel will refuse the connection. Contrast this with binding to 0.0.0.0,
 * which would listen on every network interface and expose the vulnerabilities
 * to anyone who can route packets to you. We deliberately do NOT allow that.
 *
 * The value is intentionally hard-coded to loopback and is NOT read from an
 * environment variable, so it cannot be accidentally overridden to a public
 * interface by a stray `HOST=0.0.0.0` in a shell profile.
 * -----------------------------------------------------------------------------
 */

const path = require('path');

module.exports = {
  // Loopback only. Do not change this to 0.0.0.0 or a LAN IP.
  HOST: '127.0.0.1',

  // Port is safe to configure; only affects the loopback listener.
  PORT: Number(process.env.WHL_PORT) || 3000,

  // Absolute paths used throughout the app.
  paths: {
    frontend: path.join(__dirname, '..', 'frontend'),
    // Sandbox directory that the (intentionally) vulnerable file endpoints read
    // from. It only ever contains harmless, clearly-fake sample files.
    labFiles: path.join(__dirname, 'lab-files')
  }
};
