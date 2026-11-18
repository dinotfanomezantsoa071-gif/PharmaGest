from .models import JournalAudit


def enregistrer_audit(request, action, modele_cible, objet_id='', details=''):
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    ip = x_forwarded_for.split(',')[0].strip() if x_forwarded_for else request.META.get('REMOTE_ADDR')
    utilisateur = request.user if request.user.is_authenticated else None

    JournalAudit.objects.create(
        utilisateur=utilisateur,
        action=action,
        modele_cible=modele_cible,
        objet_id=str(objet_id),
        details=details,
        adresse_ip=ip,
    )