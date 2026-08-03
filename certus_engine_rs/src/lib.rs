use ndarray::{Array1, Array2, ArrayView1, Zip};
use num_complex::Complex64;
use pyo3::prelude::*;
use numpy::{IntoPyArray, PyArray1, PyReadonlyArray1, PyReadonlyArray2, PyReadonlyArray3};
use rayon::prelude::*;

const SMALL_EPSILON: f64 = 1e-12;
const TWO_PI: f64 = 2.0 * std::f64::consts::PI;

// Stable complex trig calculation matching Python's compute_complex_phase_components
#[inline(always)]
fn compute_stable_complex_trig(phi: Complex64) -> (Complex64, Complex64) {
    let phi_r = phi.re;
    let phi_i = phi.im;
    
    // Clamp to prevent overflow for thick absorbing layers
    let phi_i_clamped = phi_i.max(-700.0).min(700.0);
    
    let exp_pos = (-phi_i_clamped).exp();
    let exp_neg = phi_i_clamped.exp();
    
    let cos_phi_r = phi_r.cos();
    let sin_phi_r = phi_r.sin();
    
    let cos_phi_real = cos_phi_r * (exp_pos + exp_neg) / 2.0;
    let cos_phi_imag = sin_phi_r * (exp_pos - exp_neg) / 2.0;
    
    let sin_phi_real = sin_phi_r * (exp_pos + exp_neg) / 2.0;
    let sin_phi_imag = cos_phi_r * (exp_neg - exp_pos) / 2.0;
    
    (
        Complex64::new(cos_phi_real, cos_phi_imag),
        Complex64::new(sin_phi_real, sin_phi_imag)
    )
}

// Helper function to compute R and T for a single wavelength (no backside, normal incidence)
#[inline(always)]
fn compute_tmm_single_point(
    k0_val: f64,
    d: &[f64],
    n_layer_row: ArrayView1<Complex64>,
    n_s: Complex64,
) -> (f64, f64, Complex64, Complex64, Complex64, Complex64) {
    let mut m00 = Complex64::new(1.0, 0.0);
    let mut m01 = Complex64::new(0.0, 0.0);
    let mut m10 = Complex64::new(0.0, 0.0);
    let mut m11 = Complex64::new(1.0, 0.0);
    
    let i_val = Complex64::new(0.0, 1.0);
    let num_layers = d.len();

    for j in 0..num_layers {
        let mut nc = n_layer_row[j];
        if nc.im > 0.0 {
            nc.im = -nc.im;
        }
        
        let phi = nc * k0_val * d[j];
        let (cp, sp) = compute_stable_complex_trig(phi);
        let isp = i_val * sp;
        
        let m01_j = if nc.norm() > SMALL_EPSILON { isp / nc } else { Complex64::new(0.0, 0.0) };
        let m10_j = isp * nc;
        
        // M_new = L @ M_old
        let new_m00 = cp * m00 + m01_j * m10;
        let new_m01 = cp * m01 + m01_j * m11;
        let new_m10 = m10_j * m00 + cp * m10;
        let new_m11 = m10_j * m01 + cp * m11;
        
        m00 = new_m00;
        m01 = new_m01;
        m10 = new_m10;
        m11 = new_m11;
    }
    
    let n0 = Complex64::new(1.0, 0.0);
    let num_r = (m00 * n0 + m01 * n0 * n_s) - (m10 + m11 * n_s);
    let den_r = (m00 * n0 + m01 * n0 * n_s) + (m10 + m11 * n_s);
    
    let mut r_val = if den_r.norm() > SMALL_EPSILON {
        let r_ampl = num_r / den_r;
        r_ampl.norm_sqr()
    } else {
        1.0
    };
    
    let mut t_val = if den_r.norm() > SMALL_EPSILON {
        let t_ampl = Complex64::new(2.0, 0.0) * n0 / den_r;
        (n_s.re / n0.re) * t_ampl.norm_sqr()
    } else {
        0.0
    };
    
    r_val = r_val.max(0.0).min(1.0);
    t_val = t_val.max(0.0).min(1.0 - r_val);
    
    (r_val, t_val, m00, m01, m10, m11)
}

#[pyfunction]
fn calculate_RT_no_backside<'py>(
    py: Python<'py>,
    thicknesses: PyReadonlyArray1<f64>,
    n_layers_complex: PyReadonlyArray2<Complex64>,
    n_sub_complex: PyReadonlyArray1<Complex64>,
    wls: PyReadonlyArray1<f64>,
) -> PyResult<(Bound<'py, PyArray1<f64>>, Bound<'py, PyArray1<f64>>)> {
    
    let d = thicknesses.as_slice()?;
    let n_layers = n_layers_complex.as_array();
    let n_sub = n_sub_complex.as_array();
    let wls_array = wls.as_array();
    let num_wav = wls_array.len();
    
    let mut r_out = Array1::<f64>::zeros(num_wav);
    let mut t_out = Array1::<f64>::zeros(num_wav);

    Zip::from(&mut r_out)
        .and(&mut t_out)
        .and(&wls_array)
        .and(n_layers.rows())
        .and(&n_sub)
        .for_each(|r, t, &wl_val, n_layer_row, &n_s| {
            let k0_val = TWO_PI / wl_val;
            let (r_val, t_val, _, _, _, _) = compute_tmm_single_point(k0_val, d, n_layer_row, n_s);
            *r = r_val;
            *t = t_val;
        });

    Ok((r_out.into_pyarray(py), t_out.into_pyarray(py)))
}

#[pyfunction]
fn calculate_RT_with_backside_fused<'py>(
    py: Python<'py>,
    thicknesses: PyReadonlyArray1<f64>,
    n_layers_complex: PyReadonlyArray2<Complex64>,
    n_sub_complex: PyReadonlyArray1<Complex64>,
    wls: PyReadonlyArray1<f64>,
) -> PyResult<(Bound<'py, PyArray1<f64>>, Bound<'py, PyArray1<f64>>)> {
    
    let d = thicknesses.as_slice()?;
    // Reversed thicknesses for backside
    let mut d_rev = d.to_vec();
    d_rev.reverse();

    let n_layers = n_layers_complex.as_array();
    let n_sub = n_sub_complex.as_array();
    let wls_array = wls.as_array();
    let num_wav = wls_array.len();
    
    let mut r_out = Array1::<f64>::zeros(num_wav);
    let mut t_out = Array1::<f64>::zeros(num_wav);

    Zip::from(&mut r_out)
        .and(&mut t_out)
        .and(&wls_array)
        .and(n_layers.rows())
        .and(&n_sub)
        .for_each(|r, t, &wl_val, n_layer_row, &n_s| {
            let k0_val = TWO_PI / wl_val;
            
            // 1. Front calculation (Air -> Stack -> Sub)
            let (rf, tf, _, _, _, _) = compute_tmm_single_point(k0_val, d, n_layer_row, n_s);
            
            // 2. Backside correction
            if n_s.im.abs() > 1e-8 {
                *r = rf;
                *t = 0.0;
                return;
            }
            
            // Reverse n_layers for the backside calc
            let num_layers = n_layer_row.len();
            let mut n_rev_row = Array1::<Complex64>::zeros(num_layers);
            for j in 0..num_layers {
                n_rev_row[j] = n_layer_row[num_layers - 1 - j];
            }
            
            let n_air = Complex64::new(1.0, 0.0);
            
            let mut m00 = Complex64::new(1.0, 0.0);
            let mut m01 = Complex64::new(0.0, 0.0);
            let mut m10 = Complex64::new(0.0, 0.0);
            let mut m11 = Complex64::new(1.0, 0.0);
            let i_val = Complex64::new(0.0, 1.0);
            
            for j in 0..num_layers {
                let mut nc = n_rev_row[j];
                if nc.im > 0.0 { nc.im = -nc.im; }
                let phi = nc * k0_val * d_rev[j];
                let (cp, sp) = compute_stable_complex_trig(phi);
                let isp = i_val * sp;
                let m01_j = if nc.norm() > SMALL_EPSILON { isp / nc } else { Complex64::new(0.0, 0.0) };
                let m10_j = isp * nc;
                let new_m00 = cp * m00 + m01_j * m10;
                let new_m01 = cp * m01 + m01_j * m11;
                let new_m10 = m10_j * m00 + cp * m10;
                let new_m11 = m10_j * m01 + cp * m11;
                m00 = new_m00; m01 = new_m01; m10 = new_m10; m11 = new_m11;
            }
            
            let n0 = n_s;
            let n_sub_back = n_air;
            let num_r = (m00 * n0 + m01 * n0 * n_sub_back) - (m10 + m11 * n_sub_back);
            let den_r = (m00 * n0 + m01 * n0 * n_sub_back) + (m10 + m11 * n_sub_back);
            let r_prime = if den_r.norm() > SMALL_EPSILON {
                (num_r / den_r).norm_sqr()
            } else {
                1.0
            };
            
            let r_b = (n_s.re - 1.0) / (n_s.re + 1.0);
            let r_sub = r_b * r_b;
            let t_sub = 1.0 - r_sub;
            
            let mut denom = 1.0 - r_prime * r_sub;
            if denom < 1e-12 { denom = 1e-12; }
            
            let mut t_tot = (tf * t_sub) / denom;
            let mut r_tot = rf + (tf * tf * r_sub) / denom;
            
            t_tot = t_tot.max(0.0).min(1.0);
            r_tot = r_tot.max(0.0).min(1.0);
            
            *r = r_tot;
            *t = t_tot;
        });

    Ok((r_out.into_pyarray(py), t_out.into_pyarray(py)))
}

// Oblique Single wavelength core calculation
// Matches _oblique_stack_rt_single
#[inline(always)]
fn compute_oblique_stack_rt_single_raw(
    wl: f64,
    n_layers_row: &[Complex64],
    d_layers: &[f64],
    sin_theta_air: f64,
    cos_theta_air: f64,
    n_inc_real: f64,
    n_exit_real: f64,
    is_s_pol: bool,
) -> (f64, f64) {
    let n_layers_count = d_layers.len();
    let mut m00 = Complex64::new(1.0, 0.0);
    let mut m01 = Complex64::new(0.0, 0.0);
    let mut m10 = Complex64::new(0.0, 0.0);
    let mut m11 = Complex64::new(1.0, 0.0);
    let i_val = Complex64::new(0.0, 1.0);
    let k = TWO_PI / wl;

    for j in 0..n_layers_count {
        let n_layer = n_layers_row[j];
        if n_layer.norm() < SMALL_EPSILON {
            return (1.0, 0.0);
        }

        let sin_theta_layer = sin_theta_air / n_layer;
        let cos_theta_layer = (1.0 - sin_theta_layer * sin_theta_layer).sqrt();

        let eta_layer = if is_s_pol {
            n_layer * cos_theta_layer
        } else {
            if cos_theta_layer.norm() < SMALL_EPSILON {
                return (1.0, 0.0);
            }
            n_layer / cos_theta_layer
        };

        if eta_layer.norm() < SMALL_EPSILON {
            return (1.0, 0.0);
        }

        let phi = n_layer * k * d_layers[j] * cos_theta_layer;
        let (cp, sp) = compute_stable_complex_trig(phi);

        let l01 = i_val * sp / eta_layer;
        let l10 = i_val * eta_layer * sp;

        let t00 = cp * m00 + l01 * m10;
        let t01 = cp * m01 + l01 * m11;
        let t10 = l10 * m00 + cp * m10;
        let t11 = l10 * m01 + cp * m11;

        m00 = t00; m01 = t01; m10 = t10; m11 = t11;
    }

    let sin_exit = sin_theta_air / n_exit_real.max(SMALL_EPSILON);
    if sin_exit > 1.0 {
        return (1.0, 0.0);
    }
    let cos_exit = (1.0 - sin_exit * sin_exit).sqrt();

    let (eta_inc, eta_exit) = if is_s_pol {
        let eta_i = if n_inc_real == 1.0 {
            n_inc_real * cos_theta_air
        } else {
            n_inc_real * (1.0 - (sin_theta_air / n_inc_real.max(SMALL_EPSILON)).powi(2)).max(0.0).sqrt()
        };
        (eta_i, n_exit_real * cos_exit)
    } else {
        let cos_inc = if n_inc_real == 1.0 {
            cos_theta_air
        } else {
            (1.0 - (sin_theta_air / n_inc_real.max(SMALL_EPSILON)).powi(2)).max(0.0).sqrt()
        };
        if cos_inc.abs() < SMALL_EPSILON || cos_exit.abs() < SMALL_EPSILON {
            return (1.0, 0.0);
        }
        (n_inc_real / cos_inc, n_exit_real / cos_exit)
    };

    let b = m00 + m01 * eta_exit;
    let c = m10 + m11 * eta_exit;

    let denom = eta_inc * b + c;
    let den2 = denom.norm_sqr();
    if den2 < SMALL_EPSILON {
        return (1.0, 0.0);
    }

    let num = eta_inc * b - c;
    let r_coeff = num / denom;
    let t_coeff = 2.0 * eta_inc / denom;

    let mut r_val = r_coeff.norm_sqr();
    let mut t_val = (eta_exit / eta_inc) * t_coeff.norm_sqr();

    r_val = r_val.max(0.0).min(1.0);
    t_val = t_val.max(0.0).min(1.0);

    (r_val, t_val)
}

#[pyfunction]
fn oblique_stack_rt_single(
    wl: f64,
    n_layers_row: PyReadonlyArray1<Complex64>,
    d_layers: PyReadonlyArray1<f64>,
    sin_theta_air: f64,
    cos_theta_air: f64,
    n_inc_real: f64,
    n_exit_real: f64,
    is_s_pol: bool,
) -> PyResult<(f64, f64)> {
    let n_row = n_layers_row.as_slice()?;
    let d = d_layers.as_slice()?;
    let (r, t) = compute_oblique_stack_rt_single_raw(wl, n_row, d, sin_theta_air, cos_theta_air, n_inc_real, n_exit_real, is_s_pol);
    Ok((r, t))
}

#[pyfunction]
fn calc_spectrum_oblique_parallel<'py>(
    py: Python<'py>,
    wls: PyReadonlyArray1<f64>,
    n_layers_complex: PyReadonlyArray2<Complex64>,
    thicknesses: PyReadonlyArray1<f64>,
    n_sub_complex: PyReadonlyArray1<Complex64>,
    angle_deg: f64,
    is_s_pol: bool,
) -> PyResult<(Bound<'py, PyArray1<f64>>, Bound<'py, PyArray1<f64>>)> {
    
    let d = thicknesses.as_slice()?;
    let n_layers = n_layers_complex.as_array();
    let n_sub = n_sub_complex.as_array();
    let wls_array = wls.as_array();
    let n_wl = wls_array.len();
    let n_layers_count = d.len();
    
    let mut r_out = Array1::<f64>::zeros(n_wl);
    let mut t_out = Array1::<f64>::zeros(n_wl);
    
    let n0 = 1.0;
    let theta0_rad = angle_deg.to_radians();
    let sin_theta0 = theta0_rad.sin();
    let cos_theta0 = theta0_rad.cos();

    Zip::from(&mut r_out)
        .and(&mut t_out)
        .and(&wls_array)
        .and(n_layers.rows())
        .and(&n_sub)
        .for_each(|r, t, &wl, n_layer_row, &n_sub_val| {
            if n_layers_count == 0 {
                let n_sub_real = n_sub_val.re;
                let sin_theta_sub = (n0 / n_sub_real) * sin_theta0;
                if sin_theta_sub > 1.0 {
                    *r = 1.0;
                    *t = 0.0;
                    return;
                }
                let cos_theta_sub = (1.0 - sin_theta_sub * sin_theta_sub).sqrt();
                let (eta_inc, eta_sub) = if is_s_pol {
                    (n0 * cos_theta0, n_sub_real * cos_theta_sub)
                } else {
                    (n0 / cos_theta0, n_sub_real / cos_theta_sub)
                };
                let r_val = (eta_inc - eta_sub) / (eta_inc + eta_sub);
                *r = r_val * r_val;
                *t = 1.0 - *r;
                return;
            }
            
            let mut m00 = Complex64::new(1.0, 0.0);
            let mut m01 = Complex64::new(0.0, 0.0);
            let mut m10 = Complex64::new(0.0, 0.0);
            let mut m11 = Complex64::new(1.0, 0.0);
            let k = TWO_PI / wl;
            let i_val = Complex64::new(0.0, 1.0);
            
            for j in 0..n_layers_count {
                let n_layer = n_layer_row[j];
                if n_layer.norm() < SMALL_EPSILON {
                    *r = 1.0; *t = 0.0;
                    return;
                }
                
                let sin_theta_layer = (n0 / n_layer) * sin_theta0;
                let cos_theta_layer = (1.0 - sin_theta_layer * sin_theta_layer).sqrt();
                
                let eta_layer = if is_s_pol {
                    n_layer * cos_theta_layer
                } else {
                    if cos_theta_layer.norm() < SMALL_EPSILON {
                        *r = 1.0; *t = 0.0;
                        return;
                    }
                    n_layer / cos_theta_layer
                };
                
                if eta_layer.norm() < SMALL_EPSILON {
                    *r = 1.0; *t = 0.0;
                    return;
                }
                
                let phi = n_layer * k * d[j] * cos_theta_layer;
                let (cp, sp) = compute_stable_complex_trig(phi);
                let l01 = i_val * sp / eta_layer;
                let l10 = i_val * eta_layer * sp;
                
                let t00 = cp * m00 + l01 * m10;
                let t01 = cp * m01 + l01 * m11;
                let t10 = l10 * m00 + cp * m10;
                let t11 = l10 * m01 + cp * m11;
                
                m00 = t00; m01 = t01; m10 = t10; m11 = t11;
            }
            
            let n_sub_real = n_sub_val.re;
            let sin_theta_sub = (n0 / n_sub_real) * sin_theta0;
            if sin_theta_sub > 1.0 {
                *r = 1.0; *t = 0.0;
                return;
            }
            let cos_theta_sub = (1.0 - sin_theta_sub * sin_theta_sub).sqrt();
            let (eta_sub, eta_inc) = if is_s_pol {
                (n_sub_real * cos_theta_sub, n0 * cos_theta0)
            } else {
                (n_sub_real / cos_theta_sub, n0 / cos_theta0)
            };
            
            let b = m00 + m01 * eta_sub;
            let c = m10 + m11 * eta_sub;
            let denom = eta_inc * b + c;
            let denom_mag_sq = denom.norm_sqr();
            if denom_mag_sq < SMALL_EPSILON {
                *r = 1.0; *t = 0.0;
                return;
            }
            
            let num = eta_inc * b - c;
            let r_coeff = num / denom;
            let r_val = r_coeff.norm_sqr().max(0.0).min(1.0);
            
            let t_coeff = 2.0 * eta_inc / denom;
            let t_val = (eta_sub / eta_inc) * t_coeff.norm_sqr();
            let t_val = t_val.max(0.0).min(1.0);
            
            *r = r_val;
            *t = t_val;
        });

    Ok((r_out.into_pyarray(py), t_out.into_pyarray(py)))
}

#[pyfunction]
fn oblique_front_char_matrix_single(
    wl: f64,
    n_layers_row: PyReadonlyArray1<Complex64>,
    d_layers: PyReadonlyArray1<f64>,
    sin_theta_air: f64,
    cos_theta_air: f64,
    is_s_pol: bool,
) -> PyResult<(Complex64, Complex64, Complex64, Complex64)> {
    let n_row = n_layers_row.as_slice()?;
    let d = d_layers.as_slice()?;
    let n_layers_count = d.len();
    
    let mut m00 = Complex64::new(1.0, 0.0);
    let mut m01 = Complex64::new(0.0, 0.0);
    let mut m10 = Complex64::new(0.0, 0.0);
    let mut m11 = Complex64::new(1.0, 0.0);
    
    if n_layers_count == 0 {
        return Ok((m00, m01, m10, m11));
    }
    
    let k = TWO_PI / wl;
    let i_val = Complex64::new(0.0, 1.0);
    let n0 = 1.0;

    for j in 0..n_layers_count {
        let n_layer = n_row[j];
        if n_layer.norm() < SMALL_EPSILON {
            let one = Complex64::new(1.0, 0.0);
            let zero = Complex64::new(0.0, 0.0);
            return Ok((one, zero, zero, one));
        }

        let sin_theta_layer = sin_theta_air / n_layer;
        let cos_theta_layer = (1.0 - sin_theta_layer * sin_theta_layer).sqrt();

        let eta_layer = if is_s_pol {
            n_layer * cos_theta_layer
        } else {
            if cos_theta_layer.norm() < SMALL_EPSILON {
                let one = Complex64::new(1.0, 0.0);
                let zero = Complex64::new(0.0, 0.0);
                return Ok((one, zero, zero, one));
            }
            n_layer / cos_theta_layer
        };

        if eta_layer.norm() < SMALL_EPSILON {
            let one = Complex64::new(1.0, 0.0);
            let zero = Complex64::new(0.0, 0.0);
            return Ok((one, zero, zero, one));
        }

        let phi = n_layer * k * d[j] * cos_theta_layer;
        let (cp, sp) = compute_stable_complex_trig(phi);
        let l01 = i_val * sp / eta_layer;
        let l10 = i_val * eta_layer * sp;

        let t00 = cp * m00 + l01 * m10;
        let t01 = cp * m01 + l01 * m11;
        let t10 = l10 * m00 + cp * m10;
        let t11 = l10 * m01 + cp * m11;

        m00 = t00; m01 = t01; m10 = t10; m11 = t11;
    }
    
    Ok((m00, m01, m10, m11))
}

#[pyfunction]
fn oblique_front_rt_from_char_matrix_nsub_real(
    m00: Complex64,
    m01: Complex64,
    m10: Complex64,
    m11: Complex64,
    n_sub_real: f64,
    sin_theta_air: f64,
    cos_theta_air: f64,
    is_s_pol: bool,
) -> PyResult<(f64, f64)> {
    let n0 = 1.0;
    if n_sub_real < SMALL_EPSILON {
        return Ok((1.0, 0.0));
    }
    
    let sin_theta_sub = (n0 / n_sub_real) * sin_theta_air;
    if sin_theta_sub > 1.0 {
        return Ok((1.0, 0.0));
    }
    
    let cos_theta_sub = (1.0 - sin_theta_sub * sin_theta_sub).sqrt();
    
    let (eta_sub, eta_inc) = if is_s_pol {
        (n_sub_real * cos_theta_sub, n0 * cos_theta_air)
    } else {
        if cos_theta_sub.abs() < SMALL_EPSILON {
            return Ok((1.0, 0.0));
        }
        (n_sub_real / cos_theta_sub, n0 / cos_theta_air)
    };
    
    let b = m00 + m01 * eta_sub;
    let c = m10 + m11 * eta_sub;
    
    let denom = eta_inc * b + c;
    let denom_mag_sq = denom.norm_sqr();
    if denom_mag_sq < SMALL_EPSILON {
        return Ok((1.0, 0.0));
    }
    
    let num = eta_inc * b - c;
    let r_coeff = num / denom;
    let r_val = r_coeff.norm_sqr().max(0.0).min(1.0);
    
    let t_coeff = 2.0 * eta_inc / denom;
    let t_val = (eta_sub / eta_inc) * t_coeff.norm_sqr();
    let t_val = t_val.max(0.0).min(1.0);
    
    Ok((r_val, t_val))
}

#[pyfunction]
fn calc_spectrum_full_oblique_exact<'py>(
    py: Python<'py>,
    wls: PyReadonlyArray1<f64>,
    d_front: PyReadonlyArray1<f64>,
    n_front_complex: PyReadonlyArray2<Complex64>,
    d_back: PyReadonlyArray1<f64>,
    n_back_complex: PyReadonlyArray2<Complex64>,
    n_sub_complex: PyReadonlyArray1<Complex64>,
    angle_deg: f64,
    is_s_pol: bool,
) -> PyResult<(Bound<'py, PyArray1<f64>>, Bound<'py, PyArray1<f64>>)> {
    
    let wls_array = wls.as_array();
    let d_f = d_front.as_slice()?;
    let n_front = n_front_complex.as_array();
    let d_b = d_back.as_slice()?;
    let n_back = n_back_complex.as_array();
    let n_sub = n_sub_complex.as_array();
    
    let n_wls = wls_array.len();
    
    let mut r_total = Array1::<f64>::zeros(n_wls);
    let mut t_total = Array1::<f64>::zeros(n_wls);
    
    let theta0_rad = angle_deg.to_radians();
    let sin_theta_air = theta0_rad.sin();
    let cos_theta_air = theta0_rad.cos();
    
    let mut d_front_rev = d_f.to_vec();
    d_front_rev.reverse();
    let mut d_back_rev = d_b.to_vec();
    d_back_rev.reverse();
    
    Zip::from(&mut r_total)
        .and(&mut t_total)
        .and(&wls_array)
        .and(n_front.rows())
        .and(n_back.rows())
        .and(&n_sub)
        .for_each(|r_tot, t_tot, &wl, n_front_row, n_back_row, &n_sub_val| {
            let n_sub_real = n_sub_val.re;
            if n_sub_real < 1e-12 {
                *r_tot = 1.0;
                *t_tot = 0.0;
                return;
            }
            
            // Forward: Air -> Front -> Sub
            let (rf, tf) = compute_oblique_stack_rt_single_raw(
                wl, n_front_row.as_slice().unwrap(), d_f, sin_theta_air, cos_theta_air, 1.0, n_sub_real, is_s_pol
            );
            
            // Reverse front: Sub -> Front -> Air
            let n_front_rev_i: Vec<Complex64> = n_front_row.iter().copied().rev().collect();
            let (rf_prime, t_front_rev) = compute_oblique_stack_rt_single_raw(
                wl, &n_front_rev_i, &d_front_rev, sin_theta_air, cos_theta_air, n_sub_real, 1.0, is_s_pol
            );
            
            // Reverse back: Sub -> Back -> Air
            let (rb_prime, tb) = if d_b.len() > 0 {
                let n_back_rev_i: Vec<Complex64> = n_back_row.iter().copied().rev().collect();
                compute_oblique_stack_rt_single_raw(
                    wl, &n_back_rev_i, &d_back_rev, sin_theta_air, cos_theta_air, n_sub_real, 1.0, is_s_pol
                )
            } else {
                // Bare substrate interface as "back stack"
                let sin_sub = sin_theta_air / n_sub_real;
                if sin_sub > 1.0 {
                    (1.0, 0.0)
                } else {
                    let cos_sub = (1.0 - sin_sub * sin_sub).sqrt();
                    let (eta_sub, eta_air) = if is_s_pol {
                        (n_sub_real * cos_sub, 1.0 * cos_theta_air)
                    } else {
                        if cos_sub.abs() < SMALL_EPSILON || cos_theta_air.abs() < SMALL_EPSILON {
                            (0.0, 0.0)
                        } else {
                            (n_sub_real / cos_sub, 1.0 / cos_theta_air)
                        }
                    };
                    let denom = eta_sub + eta_air;
                    if denom.abs() < SMALL_EPSILON {
                        (1.0, 0.0)
                    } else {
                        let rb_coeff = (eta_sub - eta_air) / denom;
                        let tb_coeff = 2.0 * eta_sub / denom;
                        let rb_val = (rb_coeff * rb_coeff).max(0.0).min(1.0);
                        let tb_val = ((eta_air / eta_sub) * tb_coeff * tb_coeff).max(0.0).min(1.0);
                        (rb_val, tb_val)
                    }
                }
            };
            
            let mut denom = 1.0 - rf_prime * rb_prime;
            if denom < 1e-12 { denom = 1e-12; }
            
            let mut t_val = (tf * tb) / denom;
            let mut r_val = rf + (tf * t_front_rev * rb_prime) / denom;
            
            t_val = t_val.max(0.0).min(1.0);
            r_val = r_val.max(0.0).min(1.0);
            
            *r_tot = r_val;
            *t_tot = t_val;
        });

    Ok((r_total.into_pyarray(py), t_total.into_pyarray(py)))
}

// =============================================================================
// ÉTAPE 2 : MODÈLES OPTIQUES
// =============================================================================

#[pyfunction]
fn sellmeier_n_array<'py>(
    py: Python<'py>,
    wls: PyReadonlyArray1<f64>,
    b1: f64,
    c1: f64,
    b2: f64,
    c2: f64,
    b3: f64,
    c3: f64,
    min_wl: f64,
) -> PyResult<Bound<'py, PyArray1<f64>>> {
    let wls_arr = wls.as_array();
    let n = wls_arr.len();
    let mut res = Array1::<f64>::zeros(n);
    
    Zip::from(&mut res)
        .and(&wls_arr)
        .for_each(|r, &wl| {
            if wl < min_wl {
                *r = 1.0;
            } else {
                let w = wl / 1000.0;
                let w2 = w * w;
                let n2 = 1.0 + b1 * w2 / (w2 - c1) + b2 * w2 / (w2 - c2) + b3 * w2 / (w2 - c3);
                *r = n2.max(1.0).sqrt();
            }
        });
        
    Ok(res.into_pyarray(py))
}

#[pyfunction]
fn get_nk_cauchy<'py>(
    py: Python<'py>,
    n4: f64,
    n7: f64,
    wls: PyReadonlyArray1<f64>,
) -> PyResult<Bound<'py, PyArray1<f64>>> {
    let wls_arr = wls.as_array();
    let n_pts = wls_arr.len();
    let mut res = Array1::<f64>::zeros(n_pts);
    
    let inv_wl1sq = 1.0 / (400.0 * 400.0);
    let inv_wl2sq = 1.0 / (700.0 * 700.0);
    let denom = inv_wl1sq - inv_wl2sq;
    let b = (n4 - n7) / denom;
    let a = n4 - b * inv_wl1sq;
    
    Zip::from(&mut res)
        .and(&wls_arr)
        .for_each(|r, &wl| {
            if wl < 1.0 {
                *r = a;
            } else {
                *r = a + b / (wl * wl);
            }
        });
        
    Ok(res.into_pyarray(py))
}

#[pyfunction]
fn get_nk_cauchy_simple(wavelength_nm: f64, n_infini: f64, a: f64) -> PyResult<f64> {
    Ok(n_infini + a / (wavelength_nm * wavelength_nm))
}

#[pyfunction]
fn epsilon2_tlu_array<'py>(
    py: Python<'py>,
    e_array: PyReadonlyArray1<f64>,
    eg: f64,
    a: f64,
    e0: f64,
    c: f64,
    eu: f64,
) -> PyResult<Bound<'py, PyArray1<f64>>> {
    let e_arr = e_array.as_array();
    let n = e_arr.len();
    let mut result = Array1::<f64>::zeros(n);
    
    let e0_sq = e0 * e0;
    let c_sq = c * c;
    let a_e0_c = a * e0 * c;
    let delta = 0.01;
    let e_edge = eg + delta;
    let e_edge_sq = e_edge * e_edge;
    let num_edge = a_e0_c * delta * delta;
    let den_edge = e_edge * ((e_edge_sq - e0_sq).powi(2) + c_sq * e_edge_sq);
    let eps2_at_edge = if den_edge > SMALL_EPSILON { num_edge / den_edge } else { 0.0 };
    let eu_safe = eu.max(1e-6);
    
    Zip::from(&mut result)
        .and(&e_arr)
        .for_each(|res, &e| {
            if e > eg {
                let e_sq = e * e;
                let diff = e - eg;
                let num = a_e0_c * diff * diff;
                let den = e * ((e_sq - e0_sq).powi(2) + c_sq * e_sq);
                *res = if den > SMALL_EPSILON { num / den } else { 0.0 };
            } else {
                if eps2_at_edge < SMALL_EPSILON {
                    *res = 0.0;
                } else {
                    let arg = (e - eg - delta) / eu_safe;
                    let arg_clamped = arg.max(-700.0).min(700.0);
                    *res = eps2_at_edge * arg_clamped.exp();
                }
            }
        });
        
    Ok(result.into_pyarray(py))
}

#[pyfunction]
fn epsilon1_tl_analytic<'py>(
    py: Python<'py>,
    e_array: PyReadonlyArray1<f64>,
    eg: f64,
    a: f64,
    e0: f64,
    c: f64,
    eps_inf: f64,
) -> PyResult<Bound<'py, PyArray1<f64>>> {
    let e_arr = e_array.as_array();
    let n = e_arr.len();
    let mut eps1_array = Array1::<f64>::zeros(n);
    
    let e0_sq = e0 * e0;
    let eg_sq = eg * eg;
    let c_sq = c * c;
    let gamma_sq = e0_sq - c_sq / 2.0;
    let alpha = (4.0 * e0_sq - c_sq).max(1e-12).sqrt();
    let denom_log_norm = ((e0_sq - eg_sq).powi(2) + c_sq * eg_sq).sqrt();
    let a_e0_c = a * e0 * c;
    let two_a_e0_c_eg = 2.0 * a_e0_c * eg;
    let inv_pi = 1.0 / std::f64::consts::PI;
    
    Zip::from(&mut eps1_array)
        .and(&e_arr)
        .for_each(|eps1, &e| {
            let e_sq = e * e;
            let mut zeta4 = (e_sq - e0_sq).powi(2) + c_sq * e_sq;
            if zeta4 < SMALL_EPSILON { zeta4 = SMALL_EPSILON; }
            let inv_zeta4 = 1.0 / zeta4;
            
            let al = (eg_sq - e0_sq) * e_sq + eg_sq * c_sq - e0_sq * (e0_sq + 3.0 * eg_sq);
            let aa = (e_sq - e0_sq) * (e0_sq + eg_sq) + eg_sq * c_sq;
            
            let mut term1 = 0.0;
            if e > SMALL_EPSILON {
                let ratio = (eg - e) / (eg + e);
                let val_log1 = if ratio.is_finite() && ratio != 0.0 { ratio.abs().ln() } else { 0.0 };
                term1 = -a_e0_c * (e_sq + eg_sq) * inv_pi * inv_zeta4 / e * val_log1;
            }
            
            let ratio2 = (eg - e) * (eg + e) / denom_log_norm;
            let val_log2 = if ratio2.is_finite() && ratio2 != 0.0 { ratio2.abs().ln() } else { 0.0 };
            let term2 = two_a_e0_c_eg * inv_pi * inv_zeta4 * val_log2;
            
            let arg_log3_num = e0_sq + eg_sq + alpha * eg;
            let arg_log3_den = e0_sq + eg_sq - alpha * eg;
            let mut term3 = 0.0;
            if arg_log3_den > SMALL_EPSILON && alpha > SMALL_EPSILON {
                term3 = (a * c * al) / (2.0 * std::f64::consts::PI * zeta4 * alpha * e0) * (arg_log3_num / arg_log3_den).ln();
            }
            
            let atan_arg1 = (2.0 * eg + alpha) / c;
            let atan_arg2 = (2.0 * eg - alpha) / c;
            let term4 = -(a * aa) * inv_pi * inv_zeta4 / e0 * (std::f64::consts::PI - atan_arg1.atan() - atan_arg2.atan());
            
            let mut term5 = 0.0;
            let atan_arg3 = 2.0 * (eg_sq - gamma_sq) / (alpha * c).max(SMALL_EPSILON);
            if alpha > SMALL_EPSILON {
                term5 = (4.0 * a * e0 * eg * (e_sq - gamma_sq)) / (std::f64::consts::PI * zeta4 * alpha) * (std::f64::consts::PI / 2.0 - atan_arg3.atan());
            }
            
            let val = eps_inf + term1 + term2 + term3 + term4 + term5;
            *eps1 = if val.is_finite() { val.max(1.0) } else { eps_inf };
        });
        
    Ok(eps1_array.into_pyarray(py))
}

#[pyfunction]
fn epsilon_to_nk<'py>(
    py: Python<'py>,
    eps1: PyReadonlyArray1<f64>,
    eps2: PyReadonlyArray1<f64>,
    n_min: f64,
    n_max: f64,
    k_max: f64,
) -> PyResult<(Bound<'py, PyArray1<f64>>, Bound<'py, PyArray1<f64>>, bool)> {
    let e1 = eps1.as_array();
    let e2 = eps2.as_array();
    let n_pts = e1.len();
    
    let mut n_arr = Array1::<f64>::zeros(n_pts);
    let mut k_arr = Array1::<f64>::zeros(n_pts);
    
    Zip::from(&mut n_arr)
        .and(&mut k_arr)
        .and(&e1)
        .and(&e2)
        .for_each(|n_val, k_val, &ev1, &ev2| {
            let eps_mag = (ev1 * ev1 + ev2 * ev2).sqrt();
            *n_val = ((eps_mag + ev1) / 2.0).max(SMALL_EPSILON).sqrt();
            *k_val = ((eps_mag - ev1) / 2.0).max(0.0).sqrt();
        });
        
    let mut is_valid = true;
    for i in 0..n_pts {
        if n_arr[i] < n_min || n_arr[i] > n_max || k_arr[i] > k_max {
            is_valid = false;
            break;
        }
    }
    
    Ok((n_arr.into_pyarray(py), k_arr.into_pyarray(py), is_valid))
}

#[pyfunction]
fn eval_spline_nk<'py>(
    py: Python<'py>,
    b: PyReadonlyArray2<f64>,
    n_knots: PyReadonlyArray1<f64>,
    k_knots: PyReadonlyArray1<f64>,
) -> PyResult<(Bound<'py, PyArray1<f64>>, Bound<'py, PyArray1<f64>>)> {
    let basis = b.as_array();
    let n_k = n_knots.as_array();
    let k_k = k_knots.as_array();
    
    let n_values = basis.dot(&n_k);
    let k_values = basis.dot(&k_k);
    
    Ok((n_values.into_pyarray(py), k_values.into_pyarray(py)))
}

// =============================================================================
// ÉTAPE 3 : OPTIMISEURS
// =============================================================================

#[pyfunction]
fn needle_scan_cached<'py>(
    py: Python<'py>,
    wls: PyReadonlyArray1<f64>,
    n_layers_complex: PyReadonlyArray2<Complex64>,
    n_needle_complex: PyReadonlyArray2<Complex64>,
    n_sub_complex: PyReadonlyArray1<Complex64>,
    ep: PyReadonlyArray1<f64>,
    tgt_vals: PyReadonlyArray1<f64>,
    tgt_weights: PyReadonlyArray1<f64>,
    step_nm: f64,
    probe_thickness: f64,
    scan_mask: PyReadonlyArray1<i64>,
) -> PyResult<(i64, f64, f64)> {
    let wls_arr = wls.as_slice()?;
    let n_layers = n_layers_complex.as_array();
    let n_needle = n_needle_complex.as_array();
    let n_sub = n_sub_complex.as_slice()?;
    let thicknesses = ep.as_slice()?;
    let targets = tgt_vals.as_slice()?;
    let weights = tgt_weights.as_slice()?;
    let mask = scan_mask.as_slice()?;
    
    let num_layers = thicknesses.len();
    let num_wav = wls_arr.len();
    let k0: Vec<f64> = wls_arr.iter().map(|&wl| TWO_PI / wl).collect();
    
    // Step 1: Forward cumulative products L
    let mut l00 = vec![Complex64::new(1.0, 0.0); (num_layers + 1) * num_wav];
    let mut l01 = vec![Complex64::new(0.0, 0.0); (num_layers + 1) * num_wav];
    let mut l10 = vec![Complex64::new(0.0, 0.0); (num_layers + 1) * num_wav];
    let mut l11 = vec![Complex64::new(1.0, 0.0); (num_layers + 1) * num_wav];
    
    for j in 0..num_layers {
        let d_j = thicknesses[j];
        for w in 0..num_wav {
            let n_j = n_layers[[w, j]];
            let phi = k0[w] * n_j * d_j;
            let (cp, sp) = compute_stable_complex_trig(phi);
            let isp = Complex64::new(0.0, 1.0) * sp;
            let m01_j = if n_j.norm() > SMALL_EPSILON { isp / n_j } else { Complex64::new(0.0, 0.0) };
            let m10_j = isp * n_j;
            
            let idx_prev = j * num_wav + w;
            let idx_curr = (j + 1) * num_wav + w;
            
            l00[idx_curr] = cp * l00[idx_prev] + m01_j * l10[idx_prev];
            l01[idx_curr] = cp * l01[idx_prev] + m01_j * l11[idx_prev];
            l10[idx_curr] = m10_j * l00[idx_prev] + cp * l10[idx_prev];
            l11[idx_curr] = m10_j * l01[idx_prev] + cp * l11[idx_prev];
        }
    }
    
    // Step 2: Backward cumulative products R
    let mut r00 = vec![Complex64::new(1.0, 0.0); num_layers * num_wav];
    let mut r01 = vec![Complex64::new(0.0, 0.0); num_layers * num_wav];
    let mut r10 = vec![Complex64::new(0.0, 0.0); num_layers * num_wav];
    let mut r11 = vec![Complex64::new(1.0, 0.0); num_layers * num_wav];
    
    for j in (0..num_layers - 1).rev() {
        let d_jp1 = thicknesses[j + 1];
        for w in 0..num_wav {
            let n_jp1 = n_layers[[w, j + 1]];
            let phi = k0[w] * n_jp1 * d_jp1;
            let (cp, sp) = compute_stable_complex_trig(phi);
            let isp = Complex64::new(0.0, 1.0) * sp;
            let m01_jp1 = if n_jp1.norm() > SMALL_EPSILON { isp / n_jp1 } else { Complex64::new(0.0, 0.0) };
            let m10_jp1 = isp * n_jp1;
            
            let idx_next = (j + 1) * num_wav + w;
            let idx_curr = j * num_wav + w;
            
            r00[idx_curr] = r00[idx_next] * cp + r01[idx_next] * m10_jp1;
            r01[idx_curr] = r00[idx_next] * m01_jp1 + r01[idx_next] * cp;
            r10[idx_curr] = r10[idx_next] * cp + r11[idx_next] * m10_jp1;
            r11[idx_curr] = r10[idx_next] * m01_jp1 + r11[idx_next] * cp;
        }
    }
    
    // Step 3: Enumerate all (layer, z) candidates
    let mut candidates = Vec::new();
    for j in 0..num_layers {
        if mask[j] == 0 {
            continue;
        }
        let d_j = thicknesses[j];
        if d_j < step_nm + 0.1 {
            continue;
        }
        let mut z = step_nm;
        while z < d_j - 0.1 {
            candidates.push((j, z));
            z += step_nm;
        }
    }
    
    if candidates.is_empty() {
        return Ok((-1, 0.0, 1e30));
    }
    
    // Step 4: Evaluate all candidates in parallel using Rayon
    let costs: Vec<f64> = candidates.par_iter().map(|&(j, z)| {
        let d_j = thicknesses[j];
        let d_right = d_j - z;
        let mut mse_sum = 0.0;
        let mut count = 0;
        let i_val = Complex64::new(0.0, 1.0);
        
        for w in 0..num_wav {
            let w_tgt = weights[w];
            if w_tgt <= 0.0 {
                continue;
            }
            
            let kk = k0[w];
            let n_j = n_layers[[w, j]];
            let n_ndl = n_needle[[w, j]];
            let ns = n_sub[w];
            
            // ── M_left(z, n_j) ──
            let phi_l = kk * n_j * z;
            let (cp_l, sp_l) = compute_stable_complex_trig(phi_l);
            let ml01 = if n_j.norm() > SMALL_EPSILON { i_val * sp_l / n_j } else { Complex64::new(0.0, 0.0) };
            let ml10 = i_val * sp_l * n_j;
            
            // T1 = M_left × L[j]
            let idx_l = j * num_wav + w;
            let t1_00 = cp_l * l00[idx_l] + ml01 * l10[idx_l];
            let t1_01 = cp_l * l01[idx_l] + ml01 * l11[idx_l];
            let t1_10 = ml10 * l00[idx_l] + cp_l * l10[idx_l];
            let t1_11 = ml10 * l01[idx_l] + cp_l * l11[idx_l];
            
            // ── M_needle(probe, n_ndl) ──
            let phi_n = kk * n_ndl * probe_thickness;
            let (cp_n, sp_n) = compute_stable_complex_trig(phi_n);
            let mn01 = if n_ndl.norm() > SMALL_EPSILON { i_val * sp_n / n_ndl } else { Complex64::new(0.0, 0.0) };
            let mn10 = i_val * sp_n * n_ndl;
            
            // T2 = M_needle × T1
            let t2_00 = cp_n * t1_00 + mn01 * t1_10;
            let t2_01 = cp_n * t1_01 + mn01 * t1_11;
            let t2_10 = mn10 * t1_00 + cp_n * t1_10;
            let t2_11 = mn10 * t1_01 + cp_n * t1_11;
            
            // ── M_right(d_right, n_j) ──
            let phi_r = kk * n_j * d_right;
            let (cp_r, sp_r) = compute_stable_complex_trig(phi_r);
            let mr01 = if n_j.norm() > SMALL_EPSILON { i_val * sp_r / n_j } else { Complex64::new(0.0, 0.0) };
            let mr10 = i_val * sp_r * n_j;
            
            // T3 = M_right × T2
            let t3_00 = cp_r * t2_00 + mr01 * t2_10;
            let t3_01 = cp_r * t2_01 + mr01 * t2_11;
            let t3_10 = mr10 * t2_00 + cp_r * t2_10;
            let t3_11 = mr10 * t2_01 + cp_r * t2_11;
            
            // T4 = R[j] × T3
            let idx_r = j * num_wav + w;
            let rr00 = r00[idx_r];
            let rr01 = r01[idx_r];
            let rr10 = r10[idx_r];
            let rr11 = r11[idx_r];
            
            let m00_tot = rr00 * t3_00 + rr01 * t3_10;
            let m01_tot = rr00 * t3_01 + rr01 * t3_11;
            let m10_tot = rr10 * t3_00 + rr11 * t3_10;
            let m11_tot = rr10 * t3_01 + rr11 * t3_11;
            
            // ── Extract T ──
            let b_val = m00_tot + m01_tot * ns;
            let c_val = m10_tot + m11_tot * ns;
            let y_val = b_val + c_val;
            
            let mut t_val = if y_val.norm() < 1e-14 {
                0.0
            } else {
                let t_coeff = 2.0 / y_val;
                let t_v = ns.re * t_coeff.norm_sqr();
                t_v.max(0.0)
            };
            
            if y_val.norm() >= 1e-14 {
                let r_coeff = (b_val - c_val) / y_val;
                let r_v = r_coeff.norm_sqr();
                if r_v + t_val > 1.0 {
                    t_val = (1.0 - r_v).max(0.0);
                }
            }
            
            if t_val.is_finite() && targets[w].is_finite() {
                let diff = t_val - targets[w];
                mse_sum += diff * diff * w_tgt;
                count += 1;
            }
        }
        
        if count >= 5 {
            mse_sum / (count as f64)
        } else {
            1e30
        }
    }).collect();
    
    // Find best candidate
    let mut best_idx = 0;
    let mut best_cost = costs[0];
    for (c, &cost) in costs.iter().enumerate().skip(1) {
        if cost < best_cost {
            best_cost = cost;
            best_idx = c;
        }
    }
    
    let (best_layer, best_z) = candidates[best_idx];
    Ok((best_layer as i64, best_z, best_cost))
}

// =============================================================================
// ÉTAPE 4 : SOLVERS ET SIMULATION DE CROISSANCE (GROWTH)
// =============================================================================

#[inline(always)]
fn fit_parabola_vertex_3points_raw(x: &[f64; 3], y: &[f64; 3]) -> (f64, f64, f64) {
    let (x1, x2, x3) = (x[0], x[1], x[2]);
    let (y1, y2, y3) = (y[0], y[1], y[2]);
    let denom = (x1 - x2) * (x1 - x3) * (x2 - x3);
    if denom.abs() < 1e-12 {
        return (0.0, 0.0, y1);
    }
    let a = (x3 * (y2 - y1) + x2 * (y1 - y3) + x1 * (y3 - y2)) / denom;
    let b = (x3 * x3 * (y1 - y2) + x2 * x2 * (y3 - y1) + x1 * x1 * (y2 - y3)) / denom;
    let c = (x2 * x3 * (x2 - x3) * y1 + x3 * x1 * (x3 - x1) * y2 + x1 * x2 * (x1 - x2) * y3) / denom;
    (a, b, c)
}

#[inline(always)]
fn solve_quadratic_target_raw(a: f64, b: f64, c: f64, target_y: f64, current_x: f64) -> f64 {
    let c_prime = c - target_y;
    if a.abs() < 1e-09 {
        if b.abs() > 1e-09 {
            return -c_prime / b;
        }
        return current_x;
    }
    let discriminant = b * b - 4.0 * a * c_prime;
    if discriminant >= 0.0 {
        let sqrt_disc = discriminant.sqrt();
        let sol1 = (-b + sqrt_disc) / (2.0 * a);
        let sol2 = (-b - sqrt_disc) / (2.0 * a);
        if (sol1 - current_x).abs() < (sol2 - current_x).abs() {
            sol1
        } else {
            sol2
        }
    } else {
        -b / (2.0 * a)
    }
}

#[inline(always)]
fn simulate_growth_single(
    p_thick_nominal: &[f64],
    i_layer: usize,
    prev_thicknesses_sim: &[f64],
    wl: f64,
    n_h: Complex64,
    n_l: Complex64,
    n_sub: Complex64,
    probe_offset: f64,
    noise_val_precalc: f64,
    non_monotonic_factor: f64,
    non_monotonic_mode: i32,
) -> (f64, f64) {
    if wl < 0.1 {
        return (p_thick_nominal[i_layer], 0.0);
    }
    
    let mut m_before_00 = Complex64::new(1.0, 0.0);
    let mut m_before_01 = Complex64::new(0.0, 0.0);
    let mut m_before_10 = Complex64::new(0.0, 0.0);
    let mut m_before_11 = Complex64::new(1.0, 0.0);
    let i_val = Complex64::new(0.0, 1.0);
    
    for j in 0..i_layer {
        let n_prev = if j % 2 == 0 { n_h } else { n_l };
        let th_prev = prev_thicknesses_sim[j];
        let phi = TWO_PI / wl * n_prev * th_prev;
        let (cp, sp) = compute_stable_complex_trig(phi);
        let son = if n_prev.norm() > SMALL_EPSILON { sp / n_prev } else { Complex64::new(0.0, 0.0) };
        let m01 = i_val * son;
        let m10 = i_val * n_prev * sp;
        
        let t00 = cp * m_before_00 + m01 * m_before_10;
        let t01 = cp * m_before_01 + m01 * m_before_11;
        let t10 = m10 * m_before_00 + cp * m_before_10;
        let t11 = m10 * m_before_01 + cp * m_before_11;
        
        m_before_00 = t00;
        m_before_01 = t01;
        m_before_10 = t10;
        m_before_11 = t11;
    }
    
    let nominal_th = p_thick_nominal[i_layer];
    let n_current = if i_layer % 2 == 0 { n_h } else { n_l };
    
    let mut is_non_monotonic = false;
    let mut t_mono = [0.0f64; 5];
    
    if nominal_th > 0.0001 {
        for k in 0..5 {
            let th_frac = (k as f64) / 4.0 * nominal_th;
            let phi_c = TWO_PI / wl * n_current * th_frac;
            let (cp_c, sp_c) = compute_stable_complex_trig(phi_c);
            let son_c = if n_current.norm() > SMALL_EPSILON { sp_c / n_current } else { Complex64::new(0.0, 0.0) };
            let m01_c = i_val * son_c;
            let m10_c = i_val * n_current * sp_c;
            
            let a00 = cp_c * m_before_00 + m01_c * m_before_10;
            let a01 = cp_c * m_before_01 + m01_c * m_before_11;
            let a10 = m10_c * m_before_00 + cp_c * m_before_10;
            let a11 = m10_c * m_before_01 + cp_c * m_before_11;
            
            let denom = a00 + n_sub * a01 + a10 + n_sub * a11;
            if denom.norm() > SMALL_EPSILON {
                t_mono[k] = 4.0 * n_sub.re / denom.norm_sqr();
            }
        }
        
        let mut diffs = [0.0f64; 4];
        for k in 0..4 {
            diffs[k] = t_mono[k + 1] - t_mono[k];
        }
        let mut flips = 0;
        let mut current_sign = 0.0;
        if diffs[0] > 1e-09 {
            current_sign = 1.0;
        } else if diffs[0] < -1e-09 {
            current_sign = -1.0;
        }
        
        for k in 1..4 {
            let mut next_sign = 0.0;
            if diffs[k] > 1e-09 {
                next_sign = 1.0;
            } else if diffs[k] < -1e-09 {
                next_sign = -1.0;
            }
            if next_sign != 0.0 {
                if current_sign != 0.0 && next_sign != current_sign {
                    flips += 1;
                }
                current_sign = next_sign;
            }
        }
        if flips > 0 {
            is_non_monotonic = true;
        }
    }
    
    let target_t_noisy = t_mono[4] + noise_val_precalc;
    let th_points = [
        (nominal_th - probe_offset).max(0.1),
        nominal_th,
        nominal_th + probe_offset
    ];
    let mut t_points = [0.0f64; 3];
    for k in 0..3 {
        let d = th_points[k];
        let phi = TWO_PI / wl * n_current * d;
        let (cp, sp) = compute_stable_complex_trig(phi);
        let son = if n_current.norm() > SMALL_EPSILON { sp / n_current } else { Complex64::new(0.0, 0.0) };
        let m01 = i_val * son;
        let m10 = i_val * n_current * sp;
        
        let a00 = cp * m_before_00 + m01 * m_before_10;
        let a01 = cp * m_before_01 + m01 * m_before_11;
        let a10 = m10 * m_before_00 + cp * m_before_10;
        let a11 = m10 * m_before_01 + cp * m_before_11;
        
        let denom = a00 + n_sub * a01 + a10 + n_sub * a11;
        if denom.norm() > SMALL_EPSILON {
            t_points[k] = 4.0 * n_sub.re / denom.norm_sqr();
        }
    }
    
    let (a_quad, b_quad, c_quad) = fit_parabola_vertex_3points_raw(&th_points, &t_points);
    let calc_thick = solve_quadratic_target_raw(a_quad, b_quad, c_quad, target_t_noisy, nominal_th);
    let error_raw = calc_thick - nominal_th;
    
    let mut dyn_encounter = 0.0;
    if nominal_th > 0.0001 {
        let mut min_val = t_mono[0];
        let mut max_val = t_mono[0];
        for &v in t_mono.iter().skip(1) {
            if v < min_val { min_val = v; }
            if v > max_val { max_val = v; }
        }
        dyn_encounter = max_val - min_val;
    }
    
    if is_non_monotonic {
        if non_monotonic_mode == 1 { // REJECT
            (nominal_th + 1000000.0, dyn_encounter)
        } else {
            let gain = non_monotonic_factor;
            ((nominal_th + error_raw / gain).max(0.0), dyn_encounter)
        }
    } else {
        ((nominal_th + error_raw).max(0.0), dyn_encounter)
    }
}

#[pyfunction]
fn compute_dynamics_kernel<'py>(
    py: Python<'py>,
    wls: PyReadonlyArray1<f64>,
    n_layers: PyReadonlyArray1<Complex64>,
    n_subs: PyReadonlyArray1<Complex64>,
    thicknesses: PyReadonlyArray1<f64>,
    m_befores: PyReadonlyArray3<Complex64>,
) -> PyResult<(
    Bound<'py, PyArray1<f64>>,
    Bound<'py, PyArray1<f64>>,
    Bound<'py, PyArray1<f64>>,
    Bound<'py, PyArray1<f64>>,
)> {
    let wls_arr = wls.as_slice()?;
    let n_lay = n_layers.as_slice()?;
    let n_sub = n_subs.as_slice()?;
    let thicks = thicknesses.as_slice()?;
    let m_bef = m_befores.as_array();
    
    let n_wls = wls_arr.len();
    let n_steps = thicks.len();
    
    let mut dynamics = Array1::<f64>::zeros(n_wls);
    let mut t_init = Array1::<f64>::zeros(n_wls);
    let mut t_final = Array1::<f64>::zeros(n_wls);
    let mut t_min = Array1::<f64>::zeros(n_wls);
    
    let i_val = Complex64::new(0.0, 1.0);
    
    // Create flat array of indices to avoid zipping > 6 producers in ndarray::Zip
    let indices: Vec<usize> = (0..n_wls).collect();
    let indices_arr = Array1::from_vec(indices);
    
    Zip::from(&mut dynamics)
        .and(&mut t_init)
        .and(&mut t_final)
        .and(&mut t_min)
        .and(&indices_arr)
        .for_each(|dyn_val, t_i, t_f, t_m, &wl_idx| {
            let wl = wls_arr[wl_idx];
            let n_layer = n_lay[wl_idx];
            let ns = n_sub[wl_idx];
            let m_b = m_bef.index_axis(ndarray::Axis(0), wl_idx);
            
            let m00 = m_b[[0, 0]];
            let m01 = m_b[[0, 1]];
            let m10 = m_b[[1, 0]];
            let m11 = m_b[[1, 1]];
            
            let mut min_t = 2.0;
            let mut max_t = -1.0;
            let mut start_t = 0.0;
            let mut end_t = 0.0;
            
            for (step_idx, &thickness) in thicks.iter().enumerate() {
                let t_current = if wl < 0.1 {
                    0.0
                } else {
                    let phi = TWO_PI / wl * n_layer * thickness;
                    let (cp, sp) = compute_stable_complex_trig(phi);
                    let isp = i_val * sp;
                    let m01_j = if n_layer.norm() > SMALL_EPSILON { isp / n_layer } else { Complex64::new(0.0, 0.0) };
                    let m10_j = isp * n_layer;
                    
                    let a00 = cp * m00 + m01_j * m10;
                    let a01 = cp * m01 + m01_j * m11;
                    let a10 = m10_j * m00 + cp * m10;
                    let a11 = m10_j * m01 + cp * m11;
                    
                    let denom = a00 + ns * a01 + a10 + ns * a11;
                    if denom.norm() > SMALL_EPSILON {
                        4.0 * ns.re / denom.norm_sqr()
                    } else {
                        0.0
                    }
                };
                
                if step_idx == 0 {
                    start_t = t_current;
                }
                if step_idx == n_steps - 1 {
                    end_t = t_current;
                }
                if t_current < min_t {
                    min_t = t_current;
                }
                if t_current > max_t {
                    max_t = t_current;
                }
            }
            
            *dyn_val = max_t - min_t;
            *t_i = start_t;
            *t_f = end_t;
            *t_m = min_t;
        });
        
    Ok((
        dynamics.into_pyarray(py),
        t_init.into_pyarray(py),
        t_final.into_pyarray(py),
        t_min.into_pyarray(py),
    ))
}

#[pyfunction]
fn update_run_states_kernel<'py>(
    py: Python<'py>,
    p_thick_nom_arr: PyReadonlyArray1<f64>,
    i_layer: i64,
    prev_stacks: PyReadonlyArray2<f64>,
    best_wl: f64,
    nh: Complex64,
    nl: Complex64,
    n_sub: Complex64,
    offset_val: f64,
    noise_values: PyReadonlyArray1<f64>,
    factor_val: f64,
    non_monotonic_mode: i32,
) -> PyResult<Bound<'py, PyArray1<f64>>> {
    let p_thick = p_thick_nom_arr.as_slice()?;
    let prev_stacks_arr = prev_stacks.as_array();
    let noises = noise_values.as_slice()?;
    
    let num_runs = prev_stacks_arr.shape()[0];
    let mut updates = Array1::<f64>::zeros(num_runs);
    let layer_idx = i_layer as usize;
    
    Zip::from(&mut updates)
        .and(prev_stacks_arr.rows())
        .and(noises)
        .par_for_each(|up, prev_stack_row, &noise| {
            let prev_stack_slice = prev_stack_row.as_slice().unwrap();
            let (updated_th, _) = simulate_growth_single(
                p_thick,
                layer_idx,
                prev_stack_slice,
                best_wl,
                nh,
                nl,
                n_sub,
                offset_val,
                noise,
                factor_val,
                non_monotonic_mode,
            );
            *up = updated_th;
        });
        
    Ok(updates.into_pyarray(py))
}

#[pymodule]
fn certus_engine(_py: Python<'_>, m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_function(wrap_pyfunction!(calculate_RT_no_backside, m)?)?;
    m.add_function(wrap_pyfunction!(calculate_RT_with_backside_fused, m)?)?;
    m.add_function(wrap_pyfunction!(oblique_stack_rt_single, m)?)?;
    m.add_function(wrap_pyfunction!(calc_spectrum_oblique_parallel, m)?)?;
    m.add_function(wrap_pyfunction!(oblique_front_char_matrix_single, m)?)?;
    m.add_function(wrap_pyfunction!(oblique_front_rt_from_char_matrix_nsub_real, m)?)?;
    m.add_function(wrap_pyfunction!(calc_spectrum_full_oblique_exact, m)?)?;
    
    // Étape 2 : Modèles Optiques
    m.add_function(wrap_pyfunction!(sellmeier_n_array, m)?)?;
    m.add_function(wrap_pyfunction!(get_nk_cauchy, m)?)?;
    m.add_function(wrap_pyfunction!(get_nk_cauchy_simple, m)?)?;
    m.add_function(wrap_pyfunction!(epsilon2_tlu_array, m)?)?;
    m.add_function(wrap_pyfunction!(epsilon1_tl_analytic, m)?)?;
    m.add_function(wrap_pyfunction!(epsilon_to_nk, m)?)?;
    m.add_function(wrap_pyfunction!(eval_spline_nk, m)?)?;
    
    // Étape 3 : Optimiseurs
    m.add_function(wrap_pyfunction!(needle_scan_cached, m)?)?;
    
    // Étape 4 : Solvers
    m.add_function(wrap_pyfunction!(compute_dynamics_kernel, m)?)?;
    m.add_function(wrap_pyfunction!(update_run_states_kernel, m)?)?;
    Ok(())
}
