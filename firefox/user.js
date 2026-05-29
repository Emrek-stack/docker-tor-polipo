// Firefox profile hardening for use with this local Tor proxy.
// Copy or symlink this file as user.js inside a dedicated Firefox profile.

// Use the container SOCKS proxy and send DNS queries through it.
user_pref("network.proxy.type", 1);
user_pref("network.proxy.socks", "127.0.0.1");
user_pref("network.proxy.socks_port", 9050);
user_pref("network.proxy.socks_version", 5);
user_pref("network.proxy.socks_remote_dns", true);
user_pref("network.proxy.no_proxies_on", "");

// Prevent common local-network and real-IP leaks.
user_pref("media.peerconnection.enabled", false);
user_pref("network.dns.disablePrefetch", true);
user_pref("network.predictor.enabled", false);
user_pref("network.prefetch-next", false);
user_pref("browser.urlbar.speculativeConnect.enabled", false);

// Reduce browser fingerprinting surface. Some websites may degrade or ask for
// additional verification when these are enabled.
user_pref("privacy.resistFingerprinting", true);
user_pref("privacy.resistFingerprinting.letterboxing", true);
user_pref("webgl.disabled", true);
user_pref("dom.battery.enabled", false);
user_pref("beacon.enabled", false);

// Avoid persistent cross-session identifiers in this dedicated profile.
user_pref("privacy.clearOnShutdown.cache", true);
user_pref("privacy.clearOnShutdown.cookies", true);
user_pref("privacy.clearOnShutdown.downloads", true);
user_pref("privacy.clearOnShutdown.formdata", true);
user_pref("privacy.clearOnShutdown.history", true);
user_pref("privacy.clearOnShutdown.offlineApps", true);
user_pref("privacy.clearOnShutdown.sessions", true);
user_pref("privacy.sanitize.sanitizeOnShutdown", true);
