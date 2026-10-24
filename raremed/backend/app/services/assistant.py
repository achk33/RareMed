"""Fixed replies for Version 0.1.

This module is the extension point for a later clinical reasoning service.
It must stay free of disease ranking, phenotype normalization, and model calls.
"""

from app.core.constants import SUPPORTED_LOCALES

_REPLIES = {
    "en": (
        "Version 0.1 saved your message and stopped there. RareMed AI does not "
        "interpret symptoms, assign phenotype terms, or suggest diseases in this "
        "release. Those steps are reserved for a later version that can show its "
        "evidence. RareMed AI is clinical decision support. It is not a clinically "
        "validated diagnostic tool."
    ),
    "fr": (
        "La version 0.1 a enregistré votre message et s'arrête ici. RareMed AI "
        "n'interprète pas les symptômes, n'attribue pas de termes de phénotype et "
        "ne propose pas de maladies dans cette version. Ces étapes sont réservées "
        "à une version ultérieure capable d'afficher ses sources. RareMed AI est "
        "une aide à la décision clinique. Ce n'est pas un outil diagnostique "
        "validé cliniquement."
    ),
    "ar": (
        "حفظ الإصدار 0.1 رسالتك وتوقف عند هذا الحد. لا يفسّر RareMed AI الأعراض، "
        "ولا يربطها بمصطلحات الأنماط الظاهرية، ولا يقترح أمراضًا في هذا الإصدار. "
        "هذه الخطوات مؤجلة إلى إصدار لاحق يستطيع إظهار أدلته. RareMed AI منصة "
        "لدعم القرار السريري، وليست أداة تشخيص معتمدة سريريًا."
    ),
    "ary": (
        "النسخة القديمة سجّلات الرسالة ووقفات هنا بلا ما تنادي النموذج. "
        "RareMed AI ما كيشرحش الأعراض وما كيقترحش الأمراض فهاد المسار. "
        "راه مساعد للقرار السريري، ماشي أداة تشخيص معتمدة سريريًا."
    ),
}


def foundation_reply(locale: str) -> str:
    if locale not in SUPPORTED_LOCALES:
        locale = "en"
    return _REPLIES[locale]
