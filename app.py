# app.py
import io
import logging
import os
import smtplib
import sys
import time
from email.mime.application import MIMEApplication
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path

import requests
from dotenv import load_dotenv
from flask import Flask, jsonify, render_template
from pypdf import PdfReader, PdfWriter
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas

load_dotenv(override=True)

# Configuration
app = Flask(__name__)
app.config["SECRET_KEY"] = os.getenv("SECRET_KEY", "dev-secret-key")

# Option pour activer/désactiver l'upload vers Grist (désactivé par défaut à cause des erreurs 500)
ENABLE_GRIST_UPLOAD = os.getenv("ENABLE_GRIST_UPLOAD", "false").lower() == "true"

# Logging avec encodage UTF-8 pour Windows
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler("pony_club.log", encoding="utf-8"),
        logging.StreamHandler(),
    ],
)

# Forcer l'encodage UTF-8 pour le StreamHandler (console Windows)
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except AttributeError:
        import codecs

        sys.stdout = codecs.getwriter("utf-8")(sys.stdout.buffer, "strict")
        sys.stderr = codecs.getwriter("utf-8")(sys.stderr.buffer, "strict")

logger = logging.getLogger(__name__)

# Configuration Grist
GRIST_BASE_URL = os.getenv("GRIST_BASE_URL")
GRIST_API_KEY = os.getenv("GRIST_API_KEY")
GRIST_DOC_ID = os.getenv("GRIST_DOC_ID")
GRIST_TABLE_ID = os.getenv("GRIST_TABLE_ID", "Formulaire_contact_OTP")

# Configuration Email BETA.gouv
SMTP_SERVER = os.getenv("SMTP_SERVER", "smtp.ox.numerique.gouv.fr")
SMTP_PORT = int(os.getenv("SMTP_PORT", 465))
IMAP_SERVER = os.getenv("IMAP_SERVER", "imap.ox.numerique.gouv.fr")
SMTP_USER = os.getenv("SMTP_USER")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD")
EMAIL_FROM = os.getenv("EMAIL_FROM")

# Chemins principaux et alternatifs
TEMPLATE_PATHS = [
    os.getenv(
        "TEMPLATE_PATH",
        r"C:\Users\james\Documents\Python files\Pony club\template\test_publi.pdf",
    ),
    os.getenv(
        "TEMPLATE_PATH_ALT",
        r"C:\Users\james.chaigneaud\Documents\API Python\Pony club\template\test_publi.pdf",
    ),
]

FONT_PATHS = [
    os.getenv(
        "FONT_PATH",
        r"C:\Users\james\Documents\Python files\Pony club\fonts\DIN-MediumAlternate.ttf",
    ),
    os.getenv(
        "FONT_PATH_ALT",
        r"C:\Users\james.chaigneaud\Documents\API Python\Pony club\fonts\DIN-MediumAlternate.ttf",
    ),
]

OUTPUT_DIRS = [
    os.getenv(
        "OUTPUT_DIR", r"C:\Users\james\Documents\Python files\Pony club\output\cartes"
    ),
    os.getenv(
        "OUTPUT_DIR_ALT",
        r"C:\Users\james.chaigneaud\Documents\API Python\Pony club\output\cartes",
    ),
]


def find_existing_path(paths_list, path_type="fichier"):
    """Cherche le premier chemin existant dans une liste."""
    for path_str in paths_list:
        path = Path(path_str)
        if path.exists():
            logger.info(f"[OK] {path_type.capitalize()} trouve : {path}")
            return path

    default_path = Path(paths_list[0])
    logger.warning(f"[!] Aucun {path_type} trouve, utilisation de : {default_path}")
    return default_path


# Trouver les chemins existants
TEMPLATE_PATH = find_existing_path(TEMPLATE_PATHS, "template")
FONT_PATH = find_existing_path(FONT_PATHS, "police")
OUTPUT_DIR = find_existing_path(OUTPUT_DIRS, "dossier de sortie")

# Créer le dossier de sortie s'il n'existe pas
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
logger.info(f"[OUTPUT] Dossier de sortie : {OUTPUT_DIR}")

# Enregistre la police
try:
    pdfmetrics.registerFont(TTFont("DinAlternate", FONT_PATH))
except Exception as e:
    logger.warning(
        f"Police DinAlternate non trouvée à l'emplacement {FONT_PATH}. Erreur : {e}"
    )

# Textes des emails
EMAIL_VIP_TEXTE = """Hey,

Grâce à ton soutien indéfectible et ta capacité à croire en un poney numérique avant même qu'il sache trotter, One Trick Pony a pu poursuivre sa chevauchée.

Et comme on ne laisse jamais un·e allié·e repartir les mains vides, voici le graal : 👉 ta carte de membre à vie du Pony Club. Comme les tatouages, mais sans douleur.

Merci pour l'élan, les échanges et les coups de boost. Le Pony t'est reconnaissant. Moi aussi.

La cavale continue 🎠✨
"""

EMAIL_VIP_HTML = """
<html>
<body style="font-family: Arial, sans-serif; font-size: 14px; color: #333;">
<p>Hey,</p>

<p>Grâce à ton soutien indéfectible et ta capacité à croire en un poney numérique avant même qu'il sache trotter, <strong>One Trick Pony</strong> a pu continuer sa chevauchée.</p>

<p>Et comme on ne laisse jamais un·e allié·e repartir les mains vides, voici le graal : 👉 ta carte de membre à vie du Pony Club. Comme les tatouages, mais sans douleur.</p>

<p>Merci pour l'élan, les échanges et les coups de boost. Le Pony t'est reconnaissant. Moi aussi.</p>

<p>La cavale continue 🎠✨</p>
</body>
</html>
"""

EMAIL_STANDARD_TEXTE = """Bonjour,

Merci d'avoir accepté de tester One Trick Pony, votre participation est précieuse pour faire progresser cette application encore en version Beta.

Veuillez trouver :
- La procédure d'installation du widget, étape par étape : https://docs.numerique.gouv.fr/docs/080ccdc1-24ab-461d-9ee2-2080df7fd871/
- L'URL d'accès à l'app à coller dans la page widget url personnalisé : https://grist-otp-adn-prod.osc-secnum-fr1.scalingo.io/

Et en pièce jointe, votre carte de membre du poney club :p

Un formulaire de retour (https://tally.so/r/QKd0Wg) est également disponible : il vous permettra de partager vos impressions, de signaler d'éventuels bugs et de proposer des pistes d'amélioration.

Selon vos retours, nous pourrons revenir vers vous pour un court échange avec notre designer UI/UX, afin d'affiner l'expérience utilisateur.

Merci encore pour le temps que vous y consacrez.

Bien à vous,
L'équipe One Trick Pony 🎠
"""

EMAIL_STANDARD_HTML = """
<html>
<body style="font-family: Arial, sans-serif; font-size: 14px; color: #333;">
<p>Bonjour,</p>

<p><strong>Merci d'avoir accepté de tester One Trick Pony, votre participation est précieuse pour faire progresser cette application encore en version Beta.</strong></p>

<p>Veuillez trouver :</p>
<ul>
<li>La procédure d'installation du widget, étape par étape : <a href="https://docs.numerique.gouv.fr/docs/080ccdc1-24ab-461d-9ee2-2080df7fd871/">lien ici</a></li>
<li>L'URL d'accès à l'app à coller dans la page widget url personnalisé : https://grist-otp-adn-prod.osc-secnum-fr1.scalingo.io/</li>
</ul>

<p>Et en pièce jointe, votre carte de membre du poney club :p</p>

<p>Un <a href="https://tally.so/r/QKd0Wg">formulaire de retour</a> est également disponible : il vous permettra de partager vos impressions, de signaler d'éventuels bugs et de proposer des pistes d'amélioration.</p>

<p>Selon vos retours, nous pourrons revenir vers vous pour un court échange avec notre designer UI/UX, afin d'affiner l'expérience utilisateur.</p>

<p>Merci encore pour le temps que vous y consacrez.</p>

<p>Bien à vous,<br>
L'équipe One Trick Pony 🎠</p>
</body>
</html>
"""


class GristAPI:
    def __init__(self):
        self.base_url = GRIST_BASE_URL
        self.headers = {
            "Authorization": f"Bearer {GRIST_API_KEY}",
            "Content-Type": "application/json",
        }

    def get_records(self, filters=None):
        """Récupère les enregistrements de Grist"""
        url = f"{self.base_url}/docs/{GRIST_DOC_ID}/tables/{GRIST_TABLE_ID}/records"

        params = {}
        if filters:
            params["filter"] = filters

        try:
            response = requests.get(url, headers=self.headers, params=params)
            response.raise_for_status()
            return response.json().get("records", [])
        except Exception as e:
            logger.error(f"Erreur récupération Grist: {e}")
            return []

    def upload_attachment(self, file_path):
        """Upload un fichier en tant que pièce jointe sur Grist."""
        url = f"{self.base_url}/docs/{GRIST_DOC_ID}/attachments"

        try:
            if not isinstance(file_path, Path):
                file_path = Path(file_path)

            if not file_path.exists():
                logger.error(f"Fichier introuvable: {file_path}")
                return None

            file_size = file_path.stat().st_size
            logger.debug(f"Taille du fichier: {file_size / 1024:.2f} KB")

            with open(file_path, "rb") as f:
                files = {"upload": (file_path.name, f, "application/pdf")}
                headers = {"Authorization": f"Bearer {GRIST_API_KEY}"}
                response = requests.post(url, headers=headers, files=files, timeout=60)

            if response.status_code != 200:
                logger.error(
                    f"Erreur HTTP {response.status_code}: {response.text[:200]}"
                )
                return None

            result = response.json()

            if isinstance(result, list) and len(result) > 0:
                attachment_id = result[0]
                logger.info(f"✓ Upload réussi, ID: {attachment_id}")
                return attachment_id

            logger.error(f"Réponse inattendue: {result}")
            return None

        except requests.exceptions.Timeout:
            logger.error(f"Timeout lors de l'upload de {file_path.name} (>60s)")
            return None
        except requests.exceptions.ConnectionError:
            logger.error("Erreur de connexion lors de l'upload")
            return None
        except Exception as e:
            logger.error(f"Erreur upload: {str(e)}")
            return None

    def update_record(self, record_id, fields):
        """Met à jour un enregistrement"""
        url = f"{self.base_url}/docs/{GRIST_DOC_ID}/tables/{GRIST_TABLE_ID}/records"

        payload = {"records": [{"id": record_id, "fields": fields}]}

        try:
            logger.debug(f"Mise à jour Grist - ID: {record_id}, Champs: {fields}")
            response = requests.patch(url, headers=self.headers, json=payload)
            response.raise_for_status()
            logger.info(f"✓ Grist mis à jour - ID {record_id}: {fields}")
            return True
        except requests.exceptions.HTTPError as e:
            logger.error(
                f"Erreur HTTP mise à jour Grist (ID {record_id}): {e.response.status_code} - {e.response.text[:200]}"
            )
            return False
        except Exception as e:
            logger.error(f"Erreur mise à jour Grist (ID {record_id}): {e}")
            return False


def create_overlay(nom, prenom, id_card):
    """Crée le calque avec les données personnalisées"""
    packet = io.BytesIO()
    page_size = (53.9 * mm, 81.4 * mm)
    can = canvas.Canvas(packet, pagesize=page_size)

    try:
        can.setFont("DinAlternate", 15)
    except Exception:
        can.setFont("Helvetica", 15)

    can.drawString(2.7, 70, nom)
    can.drawString(2.7, 55, prenom)

    try:
        can.setFont("DinAlternate", 6)
    except Exception:
        can.setFont("Helvetica", 6)

    can.drawString(119, 7.5, str(id_card))

    can.save()
    packet.seek(0)
    return PdfReader(packet)


def generate_card(record):
    """Génère une carte PDF pour un enregistrement"""
    try:
        fields = record["fields"]
        nom = fields.get("Nom", "")
        prenom = fields.get("Prenom", "")
        id_card = fields.get("Id_card", "")

        if not all([nom, prenom, id_card]):
            logger.warning(f"Données incomplètes pour l'enregistrement {record['id']}")
            return None

        template = PdfReader(TEMPLATE_PATH)
        overlay = create_overlay(nom, prenom, id_card)

        writer = PdfWriter()
        page = template.pages[0]
        page.merge_page(overlay.pages[0])
        writer.add_page(page)

        output_file = OUTPUT_DIR / f"carte_{nom}_{prenom}_{id_card}.pdf"
        with open(output_file, "wb") as output:
            writer.write(output)

        logger.info(f"✓ Carte générée : {output_file.name}")
        return output_file

    except Exception as e:
        logger.error(f"Erreur génération carte (ID {record['id']}): {e}")
        return None


def send_email(record, card_path):
    """Envoie un email avec la carte en pièce jointe"""
    try:
        fields = record["fields"]
        email = fields.get("Email", "")
        nom = fields.get("Nom", "")
        prenom = fields.get("Prenom", "")
        is_vip = fields.get("VIP", False)

        if not email:
            logger.warning(f"Pas d'email pour {nom} {prenom}")
            return False

        if is_vip:
            corps_texte = EMAIL_VIP_TEXTE
            corps_html = EMAIL_VIP_HTML
            subject = "Tu es officiellement membre du Pony Club 🐴💫"
        else:
            corps_texte = EMAIL_STANDARD_TEXTE
            corps_html = EMAIL_STANDARD_HTML
            subject = "🦄 Test One Trick Pony"

        msg = MIMEMultipart("alternative")
        msg["From"] = f"One Trick Pony <{SMTP_USER}>"
        msg["To"] = email
        msg["Subject"] = subject
        msg["Reply-To"] = SMTP_USER

        msg.attach(MIMEText(corps_texte, "plain", "utf-8"))
        msg.attach(MIMEText(corps_html, "html", "utf-8"))

        msg_complet = MIMEMultipart("mixed")
        msg_complet["From"] = msg["From"]
        msg_complet["To"] = msg["To"]
        msg_complet["Subject"] = msg["Subject"]
        msg_complet["Reply-To"] = msg["Reply-To"]
        msg_complet["Bcc"] = f"{SMTP_USER}, saliha.chekroun.ext@beta.gouv.fr"
        msg_complet.attach(msg)

        with open(card_path, "rb") as f:
            pj = MIMEApplication(f.read(), _subtype="pdf")
            pj.add_header(
                "Content-Disposition",
                "attachment",
                filename=f"carte_{nom}_{prenom}.pdf",
            )
            msg_complet.attach(pj)

        with smtplib.SMTP_SSL(SMTP_SERVER, SMTP_PORT) as server:
            server.login(SMTP_USER, SMTP_PASSWORD)
            server.send_message(msg_complet)

        logger.info(
            f"✓ Email {'VIP' if is_vip else 'standard'} envoyé à {email} (BCC: {SMTP_USER})"
        )

        time.sleep(3)

        return True

    except Exception as e:
        logger.error(f"Erreur envoi email (ID {record['id']}): {e}")
        return False


def process_cards():
    """Traite les cartes à générer et envoyer"""
    try:
        grist = GristAPI()
        results = {
            "cards_generated": 0,
            "emails_sent": 0,
            "emails_vip": 0,
            "emails_standard": 0,
            "errors": [],
        }

        logger.info("🚀 Début du traitement...")

        all_records = grist.get_records()
        logger.info(f"📊 {len(all_records)} enregistrements récupérés de Grist")

        if not all_records:
            logger.warning("⚠️ Aucun enregistrement trouvé dans Grist")
            return results

        to_generate = [
            r for r in all_records if not r["fields"].get("card_factory", True)
        ]
        to_send = [r for r in all_records if not r["fields"].get("Mail_envoye", True)]

        logger.info(
            f"📋 Cartes à générer: {len(to_generate)} | Emails à envoyer: {len(to_send)}"
        )

        # ÉTAPE 1: Génération des cartes manquantes
        if to_generate:
            logger.info(f"📄 Génération de {len(to_generate)} carte(s)...")
            for record in to_generate:
                try:
                    record_id = record["id"]
                    card_path = generate_card(record)

                    if card_path:
                        results["cards_generated"] += 1
                        update_fields = {"card_factory": True}

                        if ENABLE_GRIST_UPLOAD:
                            attachment_id = grist.upload_attachment(card_path)
                            if attachment_id:
                                update_fields["Pony_card"] = ["L", attachment_id]
                                logger.info(
                                    f"✓ Carte uploadée dans Pony_card (ID: {attachment_id})"
                                )
                            else:
                                logger.warning(
                                    "⚠️ Upload échoué, stockage du chemin local"
                                )
                                update_fields["Pony_card"] = str(card_path.absolute())
                        else:
                            update_fields["Pony_card"] = str(card_path.absolute())
                            logger.info(
                                "✓ Chemin stocké dans Pony_card (upload désactivé)"
                            )

                        grist.update_record(record_id, update_fields)
                    else:
                        results["errors"].append(
                            f"Erreur génération carte pour {record_id}"
                        )
                except Exception as e:
                    logger.error(
                        f"Erreur lors de la génération de la carte {record.get('id', '?')}: {e}"
                    )
                    results["errors"].append(f"Exception génération: {str(e)}")

        # ÉTAPE 2: Envoi des emails
        if to_send:
            logger.info(f"📧 Envoi de {len(to_send)} email(s)...")
            for record in to_send:
                try:
                    record_id = record["id"]
                    fields = record["fields"]
                    nom = fields.get("Nom", "")
                    prenom = fields.get("Prenom", "")
                    id_card = fields.get("Id_card", "")

                    card_filename = f"carte_{nom}_{prenom}_{id_card}.pdf"
                    card_path = None

                    for output_dir in OUTPUT_DIRS:
                        potential_path = Path(output_dir) / card_filename
                        if potential_path.exists():
                            card_path = potential_path
                            logger.debug(f"Carte trouvée dans : {output_dir}")
                            break

                    if not card_path:
                        card_path = OUTPUT_DIR / card_filename

                    if not card_path.exists():
                        logger.info(
                            f"Carte manquante pour {nom} {prenom}, génération..."
                        )
                        card_path = generate_card(record)
                        if card_path:
                            results["cards_generated"] += 1
                            update_fields = {"card_factory": True}

                            if ENABLE_GRIST_UPLOAD:
                                attachment_id = grist.upload_attachment(card_path)
                                if attachment_id:
                                    update_fields["Pony_card"] = ["L", attachment_id]
                                else:
                                    update_fields["Pony_card"] = str(
                                        card_path.absolute()
                                    )
                            else:
                                update_fields["Pony_card"] = str(card_path.absolute())

                            grist.update_record(record_id, update_fields)

                    if card_path and card_path.exists():
                        if send_email(record, card_path):
                            results["emails_sent"] += 1

                            if fields.get("VIP", False):
                                results["emails_vip"] += 1
                            else:
                                results["emails_standard"] += 1

                            grist.update_record(record_id, {"Mail_envoye": True})
                        else:
                            results["errors"].append(
                                f"Erreur envoi mail pour {record_id}"
                            )
                    else:
                        results["errors"].append(
                            f"Carte introuvable pour {nom} {prenom}"
                        )
                except Exception as e:
                    logger.error(
                        f"Erreur lors de l'envoi email {record.get('id', '?')}: {e}"
                    )
                    results["errors"].append(f"Exception envoi: {str(e)}")

        logger.info(
            f"🎉 Traitement terminé - Cartes: {results['cards_generated']}, Emails: {results['emails_sent']}, Erreurs: {len(results['errors'])}"
        )
        return results

    except Exception as e:
        logger.error(f"❌ ERREUR CRITIQUE dans process_cards: {e}", exc_info=True)
        return {
            "cards_generated": 0,
            "emails_sent": 0,
            "emails_vip": 0,
            "emails_standard": 0,
            "errors": [f"Erreur critique: {str(e)}"],
        }


# Routes Flask
@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/process", methods=["POST"])
def api_process():
    """Lance le traitement des cartes"""
    try:
        results = process_cards()
        return jsonify({"success": True, "results": results})
    except Exception as e:
        logger.error(f"Erreur traitement: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/api/stats", methods=["GET"])
def api_stats():
    """Récupère les statistiques"""
    try:
        grist = GristAPI()
        records = grist.get_records()

        stats = {
            "total": len(records),
            "cards_pending": len(
                [r for r in records if not r["fields"].get("card_factory", True)]
            ),
            "emails_pending": len(
                [r for r in records if not r["fields"].get("Mail_envoye", True)]
            ),
            "completed": len(
                [
                    r
                    for r in records
                    if r["fields"].get("card_factory", True)
                    and r["fields"].get("Mail_envoye", True)
                ]
            ),
            "vip_count": len([r for r in records if r["fields"].get("VIP", False)]),
        }

        return jsonify(stats)
    except Exception as e:
        logger.error(f"Erreur stats: {e}")
        return jsonify({"error": str(e)}), 500


@app.route("/api/logs", methods=["GET"])
def api_logs():
    """Récupère les derniers logs"""
    try:
        with open("pony_club.log", "r", encoding="utf-8") as f:
            lines = f.readlines()
            return jsonify({"logs": lines[-50:]})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/debug/grist", methods=["GET"])
def debug_grist():
    """Endpoint de debug pour tester la connexion Grist"""
    try:
        grist = GristAPI()

        url = f"{GRIST_BASE_URL}/docs/{GRIST_DOC_ID}/tables"
        response = requests.get(url, headers=grist.headers)

        debug_info = {
            "base_url": GRIST_BASE_URL,
            "doc_id": GRIST_DOC_ID,
            "table_id": GRIST_TABLE_ID,
            "test_url": url,
            "status_code": response.status_code,
            "api_key_set": bool(GRIST_API_KEY),
            "api_key_length": len(GRIST_API_KEY) if GRIST_API_KEY else 0,
        }

        if response.status_code == 200:
            try:
                tables = response.json().get("tables", [])
                debug_info["available_tables"] = [t["id"] for t in tables]
                debug_info["message"] = (
                    f"✓ Connexion OK - {len(tables)} table(s) trouvée(s)"
                )
                debug_info["success"] = True
            except Exception as e:
                debug_info["message"] = "✗ Réponse non-JSON"
                debug_info["error"] = str(e)
                debug_info["response_preview"] = response.text[:500]
                debug_info["success"] = False
        else:
            debug_info["message"] = "✗ Erreur de connexion"
            debug_info["error"] = response.text[:500]
            debug_info["success"] = False

        return jsonify(debug_info)

    except Exception as e:
        logger.error(f"Erreur debug Grist: {e}")
        return jsonify(
            {
                "success": False,
                "error": str(e),
                "base_url": GRIST_BASE_URL,
                "doc_id": GRIST_DOC_ID,
                "api_key_set": bool(GRIST_API_KEY),
            }
        )


if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5000)
