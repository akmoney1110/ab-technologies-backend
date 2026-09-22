# seed_milestones.py
from decimal import Decimal
from proposals.models import Proposal, ProposalMilestone

PROJECT_ID = "00cff2da-62e3-4e78-a337-49aaa9b47685"

p = Proposal.objects.get(id=PROJECT_ID)

# Clean slate
p.milestone_records.all().delete()

total = p.total_price or Decimal("0.00")
print("total_price:", total)

if total <= 0:
    print("⚠️  Proposal has no total_price. Set one first:")
    print("   p.total_price = Decimal('500000'); p.save()")
else:
    deposit  = (total * Decimal("0.30")).quantize(Decimal("0.01"))
    midway   = (total * Decimal("0.40")).quantize(Decimal("0.01"))
    delivery = (total - deposit - midway).quantize(Decimal("0.01"))

    milestones = [
        ("Deposit",              deposit,  "pending"),
        ("Development",          midway,   "pending"),
        ("Delivery & Handover",  delivery, "pending"),
    ]

    for i, (title, amount, status) in enumerate(milestones, start=1):
        m = ProposalMilestone.objects.create(
            proposal=p,
            order=i,
            title=title,
            description=f"{title} payment for {p.title}",
            amount=amount,
            payment_required=True,
            status=status,
        )
        print(f"  created #{m.order}: {m.title}  amount={m.amount}  status={m.status}")

    print("\nVerify:")
    for m in p.milestone_records.all().order_by("order"):
        print(
            f"  {m.order}. {m.title}"
            f"  amount={m.amount}"
            f"  total_paid={m.total_paid}"
            f"  outstanding={m.outstanding_balance}"
            f"  is_paid={m.is_paid}"
        )