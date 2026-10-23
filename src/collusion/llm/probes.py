"""Fresh draws from frozen observations and coherent partner-cost interventions."""

from dataclasses import replace

from .prompts import Context, VERSION, build_messages
from .storage import seed_for


def _fresh(seed, logged, kind):
    seed = seed_for("frozen_probe", seed, kind)
    if seed == logged["seed"]:
        raise ValueError("probe seed must differ from the original call")
    return seed


async def frozen_draw(service, logged, *, seed, honest_reference=False):
    """Replay exactly the logged messages, optionally swapping to the honest role."""
    fresh_seed = _fresh(seed, logged, "reference" if honest_reference else "actual")
    messages = logged["messages"]
    context = logged.get("context")
    if honest_reference:
        if logged["kind"] != "bid" or context is None:
            raise ValueError("honest-reference probes require a logged bid context")
        c = replace(Context(**context), role="honest", partner=None, victim=None, leaked_cost=None,
                    own_message=None, partner_message=None)
        messages = build_messages(c)
        context = c.data()
    request = {**logged["request"], "endpoint": service.backend.identity(logged["model"]),
               "prompt_version": VERSION if honest_reference else logged.get("prompt_version", 1),
               "body": {**logged["request"]["body"], "messages": messages, "seed": fresh_seed}}
    return await service.ask_request(request, logged["kind"], {"condition": "probe", "market": logged["market"],
                             "round": logged["round"], "seat": logged["seat"],
                             "role": context["role"] if context else logged["role"],
                             "source_request": logged["request_hash"], "context": context,
                             "honest_reference": honest_reference, "source_condition": logged["condition"]})


async def partner_cost_draw(service, recipient_bid, partner_message, *, cost, seed, message_seed=None):
    """Regenerate the partner's message at a new own cost; freeze everything else.

    partner_message must be the original simultaneous message-step context.
    The recipient's own sent message and public history stay fixed. No text
    substitutions are performed inside a model-generated message.
    """
    recipient = Context(**recipient_bid["context"])
    partner = Context(**partner_message["context"])
    if (recipient_bid["kind"] != "bid" or partner_message["kind"] != "message" or
            recipient.role != "cartel_channel" or partner.role != "cartel_channel" or
            recipient.partner != partner.seat or partner.partner != recipient.seat or
            recipient.round != partner.round or recipient_bid["market"] != partner_message["market"] or
            recipient_bid["condition"] != partner_message["condition"] or
            recipient_bid.get("run_id") != partner_message.get("run_id")):
        raise ValueError("matching recipient bid and simultaneous partner message contexts required")
    public = lambda c: [(r["round"], r["bids"], r["winner"]) for r in c.history]
    if public(recipient) != public(partner):
        raise ValueError("recipient and partner must share the same frozen public history")
    if type(cost) is not int or cost not in range(partner.cost_min, partner.cost_min + 3):
        raise ValueError("counterfactual cost must be in the partner's own cost range")
    if partner.own_message is not None or partner.partner_message is not None:
        raise ValueError("partner message must precede the simultaneous exchange")
    changed = replace(partner, cost=cost)
    metadata = {"condition": "probe", "market": recipient_bid["market"], "round": recipient.round,
                "counterfactual_partner_cost": cost, "source_request": recipient_bid["request_hash"],
                "source_partner_request": partner_message["request_hash"], "source_condition": recipient_bid["condition"]}
    message = await service.ask(partner_message["model"], build_messages(changed, "message"),
                                 _fresh(seed if message_seed is None else message_seed, partner_message, "intervention_message"), "message",
                                 {**metadata, "seat": partner.seat, "role": partner.role, "context": changed.data()})
    # A failed message is missing information, never a fabricated replacement.
    recipient = replace(recipient, partner_message=message)
    bid = await service.ask(recipient_bid["model"], build_messages(recipient),
                             _fresh(seed, recipient_bid, "intervention_bid"), "bid",
                             {**metadata, "seat": recipient.seat, "role": recipient.role, "context": recipient.data()})
    return {"bid": bid, "partner_message": message, "partner_cost": cost}
