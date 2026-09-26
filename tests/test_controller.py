import pytest

from simeval import controller as ctl


def m(occ, q=0):
    return ctl.Measurement(t=30.0, occupancy_pct=occ, ramp_queue_veh=q)


def test_alinea_integrates_occupancy_error_with_correct_sign():
    a = ctl.Alinea(target_occ_pct=12.0, k_r=70.0, r0=900.0)
    assert a.update(m(10.0)) == pytest.approx(900 + 70 * 2)     # below target -> meter releases more
    b = ctl.Alinea(target_occ_pct=12.0, k_r=70.0, r0=900.0)
    assert b.update(m(15.0)) == pytest.approx(900 - 70 * 3)     # above target -> meter restricts


def test_alinea_clips_and_queue_override():
    a = ctl.Alinea(r0=300.0)
    assert a.update(m(40.0)) == ctl.R_MIN
    a = ctl.Alinea(r0=1700.0)
    assert a.update(m(0.0)) == ctl.R_MAX
    a = ctl.Alinea(r0=600.0, queue_limit_veh=25)
    assert a.update(m(40.0, q=25)) == ctl.R_MIN      # at the limit: no override
    assert a.update(m(40.0, q=26)) == ctl.R_MAX      # above the limit: flush


def test_red_time_for_rate():
    assert ctl.red_time_for_rate(720.0) == pytest.approx(5.0 - ctl.GREEN_S)
    assert ctl.red_time_for_rate(ctl.R_MAX) is None
    assert ctl.red_time_for_rate(1790.0) == pytest.approx(0.5)  # floor on red


def test_fixed_and_none_ignore_measurements():
    assert ctl.FixedTime(720).update(m(80, 40)) == 720
    assert ctl.NoControl().update(m(80, 40)) == ctl.R_MAX
    with pytest.raises(ValueError):
        ctl.make("bogus")
