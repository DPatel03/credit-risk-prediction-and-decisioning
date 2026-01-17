def decision_from_pd(pd, t_approve=0.05, t_review=0.15):
    """
    Convert calibrated probability of default (PD) into a business decision.
    """
    if pd < t_approve:
        return "APPROVE"
    elif pd < t_review:
        return "REVIEW"
    else:
        return "REJECT"
