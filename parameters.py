def get_planner_params(tuning_label):
    """
    Returns (max_vel_theta, security_dist) based on tuning_label.
    It is possible to modify the parameters here to make them easily configurable.
    """
    mapping = {
        "low":    (0.5,  0.5),
        "medium": (0.75, 0.3),
        "high":   (1.0,  0.15)
    }
    # fallback: medium f the label is not recognised
    return mapping.get(tuning_label, (0.75, 0.3))
