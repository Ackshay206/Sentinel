"""The pre-loaded scam taxonomy — Sentinel's domain knowledge.

This is what separates Sentinel from a spam-word filter: scams are modeled as a
*staged trajectory* along TWO axes that the dataset made obvious —

  Axis A — `scam_type`  : the PRETEXT (who the caller pretends to be / the lure).
  Axis B — `payment_vector` : the ASK (the irreversible payment / credential /
                              device-control they steer toward). Across every
                              scam type in the data, the call ends in one of a
                              small set of asks — gift cards, wire, crypto, bank
                              or card details, an OTP code, an upfront fee,
                              remote access, or cash to a courier. That ask is
                              the real danger, independent of the pretext.

The escalation arc (the stage):

    benign  →  authority  →  urgency  →  secrecy  →  payment

  - authority : caller asserts a position of power/trust, OR a too-good lure
                (bank, IRS, police, Microsoft, a grandchild, "you've won / been
                approved").
  - urgency   : manufactured time pressure / fear ("act now or you'll be
                arrested / lose it / your computer is infected").
  - secrecy   : pressure to keep it private / stay on the line / not consult anyone.
  - payment   : push toward a `payment_vector` — the irreversible transfer or
                credential/control hand-over.

`STAGES` is ordered; `STAGE_RANK` gives each a numeric rank used by the risk
state machine. `SCRIPTS` is a compact, data-derived library of staged patterns.
"""

from __future__ import annotations

# --- Axis: escalation stage (ordered) -------------------------------------
STAGES: list[str] = ["benign", "authority", "urgency", "secrecy", "payment"]
STAGE_RANK: dict[str, int] = {stage: i for i, stage in enumerate(STAGES)}

STAGE_DESCRIPTIONS: dict[str, str] = {
    "benign": "Ordinary conversation. No social-engineering pressure detected.",
    "authority": "Caller asserts authority/trust or dangles a lure (prize, grant, loan, refund) to lower the victim's guard.",
    "urgency": "Caller manufactures time pressure, fear, or a crisis to force a fast decision.",
    "secrecy": "Caller pressures the victim to keep it secret, stay on the line, or not consult anyone.",
    "payment": "Caller pushes toward an irreversible ask: a payment, credentials, or control of the device (see PAYMENT VECTORS).",
}

# --- Axis A: scam type (the pretext / lure) --------------------------------
SCAM_TYPES: list[str] = [
    "none",
    "grandparent",
    "bank_impersonation",
    "irs_government",
    "government_grant",
    "tech_support",
    "refund",
    "subscription_renewal",
    "delivery_package",
    "loan_debt",
    "investment_crypto",
    "pig_butchering",
    "prize_lottery",
    "charity",
    "auto_warranty",
    "job_employment",
    "utility_shutoff",
    "unknown",
]

# --- Axis B: payment vector (the irreversible ask) -------------------------
PAYMENT_VECTORS: list[str] = [
    "none",
    "gift_card",
    "wire_transfer",
    "crypto_wallet",
    "bank_or_card_details",
    "otp_code",
    "upfront_fee",
    "remote_access",
    "courier_cash",
]

PAYMENT_VECTOR_DESCRIPTIONS: dict[str, str] = {
    "none": "No irreversible ask yet.",
    "gift_card": "Buy gift cards (Apple/Google Play/Amazon) and read out the codes.",
    "wire_transfer": "Wire money or bank-transfer to an account.",
    "crypto_wallet": "Send cryptocurrency to a wallet / deposit on a crypto platform.",
    "bank_or_card_details": "Hand over bank account, debit/credit card number, or CVV.",
    "otp_code": "Read out a one-time passcode / verification code from a text.",
    "upfront_fee": "Pay a fee up front (processing, customs, taxes, insurance) to release promised money/goods.",
    "remote_access": "Install remote-access software or grant control of the device.",
    "courier_cash": "Hand cash/valuables to a courier or mail them.",
}

# Compact library of staged scam scripts (data-derived). Cues are paraphrasable
# intent markers, not literal keywords. `vectors` lists the payment vectors this
# scam type typically ends in.
SCRIPTS: list[dict] = [
    {
        "scam_type": "grandparent",
        "summary": "Caller poses as a grandchild (or their lawyer/officer) in sudden trouble.",
        "vectors": ["wire_transfer", "gift_card", "courier_cash"],
        "authority": ["it's me, your grandson", "I'm a lawyer/officer calling for your grandchild"],
        "urgency": ["I'm in jail", "I had an accident", "I need help right now"],
        "secrecy": ["don't tell mom and dad", "please keep this between us"],
        "payment": ["post bail with gift cards", "wire the money", "a courier will collect the cash"],
    },
    {
        "scam_type": "bank_impersonation",
        "summary": "Caller claims to be the victim's bank fraud/security department.",
        "vectors": ["bank_or_card_details", "otp_code", "wire_transfer"],
        "authority": ["this is your bank's fraud department", "we detected suspicious activity"],
        "urgency": ["your account will be drained", "we must stop the transfer now"],
        "secrecy": ["do not discuss this with branch staff", "stay on the line"],
        "payment": ["move your money to a 'safe account'", "confirm the code we just texted you", "verify your card number and CVV"],
    },
    {
        "scam_type": "irs_government",
        "summary": "Caller claims to be IRS / tax authority / Social Security / police with a penalty or warrant. Often invents an official-sounding body (e.g. a 'US Tax Department') that does not exist.",
        "vectors": ["gift_card", "wire_transfer", "bank_or_card_details"],
        "authority": ["this is the IRS / Social Security Administration", "a warrant has been issued", "this is a non-existent-sounding 'US tax department'"],
        "urgency": ["you will be arrested today", "your social security number is suspended"],
        "secrecy": ["do not hang up or you'll be arrested", "this is a confidential federal matter"],
        "payment": ["pay the back taxes with gift cards", "settle via wire transfer", "confirm your bank details for the 'fine'"],
    },
    {
        "scam_type": "government_grant",
        "summary": "Caller claims you've won a free government grant — usually via an invented agency that does not exist ('US Grants Department', 'Federal Grants Administration'). Real federal grants are at grants.gov; the government NEVER cold-calls offering grants.",
        "vectors": ["upfront_fee", "gift_card", "bank_or_card_details"],
        "authority": ["I'm from the US Grants Department", "you've been approved for a $9,000 government grant", "your name was selected from the federal grant list"],
        "urgency": ["the grant funds expire today", "only a few grants left"],
        "secrecy": ["this is a special program, keep your approval code private"],
        "payment": ["pay a small processing/delivery fee with gift cards", "give your bank details to deposit the grant"],
    },
    {
        "scam_type": "tech_support",
        "summary": "Caller claims the victim's computer is infected / account hacked and must be fixed remotely.",
        "vectors": ["remote_access", "gift_card", "bank_or_card_details"],
        "authority": ["this is Microsoft/Apple support", "we detected a virus on your computer"],
        "urgency": ["hackers are in your account right now", "your files will be deleted"],
        "secrecy": ["don't shut down or call your bank yet", "stay on the call while we fix it"],
        "payment": ["install this remote-access app", "buy gift cards for the security license"],
    },
    {
        "scam_type": "refund",
        "summary": "Fake 'refund/billing department' says you're owed a refund or were overcharged, then engineers a refund-reversal (often pairs with remote access to fake an 'overpayment').",
        "vectors": ["remote_access", "bank_or_card_details", "gift_card"],
        "authority": ["this is the refund department of <company>", "we're issuing you a refund for a billing error"],
        "urgency": ["we accidentally refunded too much — you must return the overpayment", "the refund window closes today"],
        "secrecy": ["stay on the line while we process it", "don't contact your bank yet"],
        "payment": ["let us remote in to issue the refund", "buy gift cards to repay the overage", "confirm your bank account and the code we sent"],
    },
    {
        "scam_type": "subscription_renewal",
        "summary": "Fake auto-renewal charge (antivirus/Amazon/etc.): 'you were charged $X, call to cancel/refund' — a funnel into a refund or remote-access scam.",
        "vectors": ["remote_access", "bank_or_card_details"],
        "authority": ["your <product> subscription has auto-renewed", "a charge of $500 was placed on your account"],
        "urgency": ["call now to cancel before it processes"],
        "secrecy": ["stay on the line while we reverse it"],
        "payment": ["let us remote in to process the cancellation", "confirm your card to reverse the charge"],
    },
    {
        "scam_type": "delivery_package",
        "summary": "Fake parcel/delivery notice (USPS/FedEx/Amazon/customs): a package is held pending a small fee or your details.",
        "vectors": ["upfront_fee", "bank_or_card_details"],
        "authority": ["this is the postal/delivery service", "a package addressed to you is held at customs"],
        "urgency": ["it will be returned today unless you act", "final delivery attempt"],
        "secrecy": [],
        "payment": ["pay a small customs/redelivery fee with your card", "confirm your card to release the parcel"],
    },
    {
        "scam_type": "loan_debt",
        "summary": "Advance-fee loan or debt-relief: you're 'approved' for a loan or can clear your debt, but must pay an upfront fee or share bank details first.",
        "vectors": ["upfront_fee", "bank_or_card_details"],
        "authority": ["you've been pre-approved for a loan", "this is the debt-relief / loan department"],
        "urgency": ["the offer expires today", "rates go up after today"],
        "secrecy": [],
        "payment": ["pay an upfront processing/insurance fee", "share your bank account so we can deposit the loan"],
    },
    {
        "scam_type": "investment_crypto",
        "summary": "High-return investment / crypto pitch promising guaranteed or doubled profits; steers you to deposit funds or buy crypto.",
        "vectors": ["crypto_wallet", "wire_transfer", "bank_or_card_details"],
        "authority": ["I help people earn huge returns", "this is an exclusive investment opportunity", "our fund doubles your money"],
        "urgency": ["the window closes soon", "the price is about to jump"],
        "secrecy": ["keep this between us", "don't let your bank talk you out of it"],
        "payment": ["deposit into this trading platform", "send USDT to this wallet", "wire your initial investment"],
    },
    {
        "scam_type": "pig_butchering",
        "summary": "Long-con romance/relationship grooming that pivots into a crypto/investment 'opportunity' the victim is coaxed to fund.",
        "vectors": ["crypto_wallet", "wire_transfer"],
        "authority": ["we've grown close — I want to help you prosper", "my uncle runs a trading firm"],
        "urgency": ["this opportunity closes soon", "you'll miss the window"],
        "secrecy": ["let's keep our finances between us"],
        "payment": ["deposit into this crypto platform I set up for you", "send the funds to this wallet"],
    },
    {
        "scam_type": "prize_lottery",
        "summary": "Caller says you've won a prize/lottery/free vacation, but must pay a fee or give card details to 'claim' it.",
        "vectors": ["upfront_fee", "gift_card", "bank_or_card_details"],
        "authority": ["you've been selected as a winner", "this is the prize claims department"],
        "urgency": ["claim within 24 hours or forfeit"],
        "secrecy": ["keep it confidential until taxes are paid"],
        "payment": ["pay the processing/customs fee with gift cards", "give your card for 'verification' to release the prize"],
    },
    {
        "scam_type": "charity",
        "summary": "Fake charity/donation appeal — pressure to donate now via card or gift cards, often citing 'your previous donations' or a disaster.",
        "vectors": ["bank_or_card_details", "gift_card"],
        "authority": ["we're calling on behalf of a charity / veterans / disaster relief", "thank you for your past donations"],
        "urgency": ["the campaign ends tonight", "victims need help right now"],
        "secrecy": [],
        "payment": ["donate now with your credit card", "buy gift cards for the donation"],
    },
    {
        "scam_type": "auto_warranty",
        "summary": "Vehicle extended-warranty robocall: your warranty is 'expiring', renew now with card + vehicle details.",
        "vectors": ["bank_or_card_details"],
        "authority": ["calling about your vehicle's extended warranty", "our records show your warranty is expiring"],
        "urgency": ["this is your final notice", "coverage lapses today"],
        "secrecy": [],
        "payment": ["give your card to lock in the renewal rate"],
    },
    {
        "scam_type": "job_employment",
        "summary": "Work-from-home / easy-money job offer that asks for bank/wallet details or an upfront fee to 'secure the position' (often money-mule recruitment).",
        "vectors": ["bank_or_card_details", "upfront_fee", "crypto_wallet"],
        "authority": ["we're hiring for simple work-from-home roles", "you've been selected for a position"],
        "urgency": ["limited positions — secure your spot today"],
        "secrecy": [],
        "payment": ["submit your bank account or wallet to set up payroll", "pay a small onboarding/equipment fee"],
    },
    {
        "scam_type": "utility_shutoff",
        "summary": "Caller threatens to cut off power/water/gas over an unpaid bill unless paid immediately.",
        "vectors": ["gift_card", "bank_or_card_details", "upfront_fee"],
        "authority": ["this is your electric company", "your account is past due"],
        "urgency": ["your power will be shut off within the hour", "a truck is on the way to disconnect you"],
        "secrecy": ["pay directly with me, not online"],
        "payment": ["pay immediately with a prepaid/gift card", "make a payment over the phone right now"],
    },
]


def build_taxonomy_brief() -> str:
    """A compact, human-readable summary of the taxonomy for the classifier prompt."""
    lines: list[str] = []
    lines.append("STAGES (escalating):")
    for stage in STAGES:
        lines.append(f"  - {stage} (rank {STAGE_RANK[stage]}): {STAGE_DESCRIPTIONS[stage]}")
    lines.append("")
    lines.append("PAYMENT VECTORS (the irreversible ask — set `payment_vector` to the one being pushed, else 'none'):")
    for vec in PAYMENT_VECTORS:
        if vec == "none":
            continue
        lines.append(f"  - {vec}: {PAYMENT_VECTOR_DESCRIPTIONS[vec]}")
    lines.append("")
    lines.append("KNOWN SCAM TYPES (pretext → typical cues per stage; vectors they end in):")
    for s in SCRIPTS:
        vecs = ", ".join(s.get("vectors", []))
        lines.append(f"  * {s['scam_type']} — {s['summary']} [vectors: {vecs}]")
        for stage in ("authority", "urgency", "secrecy", "payment"):
            cues = "; ".join(s.get(stage, []))
            if cues:
                lines.append(f"      {stage}: {cues}")
    return "\n".join(lines)
