// ============================================
// PONY CLUB - APPLICATION JAVASCRIPT
// ============================================

// Initialisation au chargement
document.addEventListener("DOMContentLoaded", function () {
  loadStats();
  loadLogs();

  // Auto-refresh toutes les 10 secondes
  setInterval(loadStats, 10000);
});

// ============================================
// STATISTIQUES
// ============================================

function loadStats() {
  fetch("/api/stats")
    .then((response) => response.json())
    .then((data) => {
      document.getElementById("stat-total").textContent = data.total || 0;
      document.getElementById("stat-vip").textContent = data.vip_count || 0;
      document.getElementById("stat-pending").textContent =
        data.cards_pending || 0;
      document.getElementById("stat-emails").textContent =
        data.emails_pending || 0;
      document.getElementById("stat-completed").textContent =
        data.completed || 0;
    })
    .catch((error) => {
      console.error("Erreur chargement stats:", error);
    });
}

// ============================================
// LOGS
// ============================================

function loadLogs() {
  fetch("/api/logs")
    .then((response) => response.json())
    .then((data) => {
      const container = document.getElementById("logs-container");
      container.innerHTML = "";

      if (data.logs && data.logs.length > 0) {
        data.logs.forEach((log) => {
          const div = document.createElement("div");
          div.className = "log-line";

          // Détection du type de log
          if (log.includes("ERROR")) {
            div.classList.add("error");
          } else if (log.includes("[OK]") || log.includes("SUCCESS")) {
            div.classList.add("success");
          } else if (log.includes("WARNING") || log.includes("[!]")) {
            div.classList.add("warning");
          } else {
            div.classList.add("info");
          }

          div.textContent = log;
          container.appendChild(div);
        });

        // Scroll vers le bas
        container.scrollTop = container.scrollHeight;
      } else {
        container.innerHTML =
          '<div class="log-line info">Aucun log disponible</div>';
      }
    })
    .catch((error) => {
      console.error("Erreur chargement logs:", error);
    });
}

// ============================================
// TRAITEMENT DES CARTES
// ============================================

function processCards() {
  const btn = document.getElementById("process-btn");
  const spinner = document.getElementById("spinner");
  const statusMsg = document.getElementById("status-message");

  // Désactiver le bouton et afficher le spinner
  btn.disabled = true;
  spinner.style.display = "inline-block";
  statusMsg.style.display = "none";

  fetch("/api/process", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
  })
    .then((response) => {
      console.log("Response status:", response.status);

      if (!response.ok) {
        throw new Error(`HTTP ${response.status}: ${response.statusText}`);
      }
      return response.json();
    })
    .then((data) => {
      console.log("Response data:", data);

      // Réactiver le bouton
      btn.disabled = false;
      spinner.style.display = "none";

      if (data.success) {
        statusMsg.className = "status-message success";

        let message =
          '<strong><img src="/static/icons/check.svg" class="inline-icon">Traitement terminé !</strong><br>';
        message += `<img src="/static/icons/card.svg" class="inline-icon">Cartes générées : <strong>${data.results.cards_generated}</strong><br>`;
        message += `<img src="/static/icons/email.svg" class="inline-icon">Emails envoyés : <strong>${data.results.emails_sent}</strong>`;

        if (data.results.emails_vip > 0) {
          message += ` (${data.results.emails_vip} <img src="/static/icons/vip.svg" style="width:16px; height:16px; vertical-align:middle;"> VIP, ${data.results.emails_standard} standard)`;
        }

        if (data.results.emails_vip > 0) {
          message += ` (${data.results.emails_vip} <img src="/static/icons/vip.svg" style="width:16px; height:16px; vertical-align:middle;"> VIP, ${data.results.emails_standard} standard)`;
        }

        statusMsg.innerHTML = message;
      } else {
        statusMsg.className = "status-message error";
        statusMsg.innerHTML = `<strong>❌ Erreur :</strong> ${
          data.error || "Erreur inconnue"
        }`;
      }

      statusMsg.style.display = "block";

      // Recharger les stats et logs
      loadStats();
      loadLogs();
    })
    .catch((error) => {
      console.error("Error:", error);

      btn.disabled = false;
      spinner.style.display = "none";

      statusMsg.className = "status-message error";
      statusMsg.innerHTML = `<strong>❌ Erreur :</strong> ${error.message}<br><small>Vérifiez la console (F12) et les logs du serveur</small>`;
      statusMsg.style.display = "block";
    });
}

// ============================================
// TEST CONNEXION GRIST
// ============================================

function testGristConnection() {
  const debugMsg = document.getElementById("debug-message");
  debugMsg.style.display = "block";
  debugMsg.className = "status-message info";
  debugMsg.textContent = "🔄 Test en cours...";

  fetch("/api/debug/grist")
    .then((response) => response.json())
    .then((data) => {
      if (data.success) {
        debugMsg.className = "status-message success";

        let message = `<strong>✅ ${data.message}</strong><br>`;
        message += `📊 Document ID: <code>${data.doc_id}</code><br>`;
        message += `📋 Table configurée: <code>${data.table_id}</code><br>`;
        message += `📋 Tables disponibles: ${data.available_tables.join(
          ", "
        )}<br>`;
        message += `🔑 API Key: ${
          data.api_key_set
            ? "✓ configurée (" + data.api_key_length + " caractères)"
            : "✗ manquante"
        }`;

        if (!data.available_tables.includes(data.table_id)) {
          message += `<br><br><strong>⚠️ ATTENTION:</strong> La table "${data.table_id}" n'existe pas!<br>Utilise une des tables ci-dessus dans ton .env`;
        } else {
          message += "<br>✓ La table existe";
        }

        debugMsg.innerHTML = message;
      } else {
        debugMsg.className = "status-message error";

        let message = `<strong>❌ ${data.message}</strong><br>`;
        message += `🔗 Base URL: ${data.base_url}<br>`;
        message += `📊 Doc ID: ${data.doc_id}<br>`;
        message += `🔑 API Key: ${
          data.api_key_set ? "✓ présente" : "❌ MANQUANTE"
        }<br>`;
        message += `📡 Status HTTP: ${data.status_code || "N/A"}`;

        if (data.error) {
          message += `<br><br><pre style="font-size: 0.8em; max-height: 150px; overflow-y: auto; background: #f5f5f5; padding: 10px; border-radius: 5px; margin-top: 0.5rem;">${data.error}</pre>`;
        }

        debugMsg.innerHTML = message;
      }
    })
    .catch((error) => {
      debugMsg.className = "status-message error";
      debugMsg.innerHTML = `<strong>❌ Erreur test :</strong> ${error}`;
    });
}
