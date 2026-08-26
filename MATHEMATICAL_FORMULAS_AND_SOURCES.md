# 📐 AAPTIRAKSHAK (SIH26001) — Mathematical Formulas & Scientific Sources

This handbook documents the complete mathematical foundations, equations, variable definitions, and peer-reviewed academic sources used across the **AAPTIRAKSHAK Early Warning System**.

---

# 1. The Coupled Two-Layer Probability Fusion Formula

### 📝 Mathematical Formulation:
$$P_{\text{final}}(c, t) = LSI_{\text{static}}(c) \times \sigma\Big(w_1 R_{3\text{d}}(c, t) + w_2 R_{1\text{d}}(c, t) + w_3 \theta_{\text{soil}}(c, t) - \beta\Big)$$

$$\text{where } \sigma(z) = \frac{1}{1 + e^{-z}}$$

### 🔍 Variable Definitions:
* $P_{\text{final}}(c, t) \in [0, 1]$: Final landslide failure probability for spatial cell $c$ at time $t$.
* $LSI_{\text{static}}(c) \in [0, 1]$: Layer 1 Landslide Susceptibility Index derived from 13 static geological conditioning factors.
* $R_{3\text{d}}(c, t)$: 3-day antecedent cumulative rainfall ($\text{mm}$).
* $R_{1\text{d}}(c, t)$: 1-day peak burst rainfall ($\text{mm}$).
* $\theta_{\text{soil}}(c, t)$: NASA SMAP root-zone soil moisture saturation percentage ($0 - 100\%$).
* $w_1 = 0.038$: Antecedent rain infiltration coefficient.
* $w_2 = 0.052$: Peak burst rainfall coefficient.
* $w_3 = 0.045$: Soil moisture pore saturation coefficient.
* $\beta = 4.2$: Critical terrain stability threshold offset.

### 📚 Academic Source & Citation:
* **Source:** Adapted from the **NASA LHASA 2.0 Global Framework** & Italian National Early Warning System (SANF).
* **Reference:** Emberson, R., Kirschbaum, D., & Stanley, T. (2020). *Global Landslide Hazard Assessment for Situational Awareness (LHASA Version 2.0)*. **AGU Earth's Future**, 8(11), e2019EF001467.  
  🔗 [https://doi.org/10.1029/2019EF001467](https://doi.org/10.1029/2019EF001467)

---

# 2. Mohr-Coulomb Soil Shear Failure & Pore-Water Pressure

### 📝 Mathematical Formulation:
$$\tau_f = c' + (\sigma_n - u_w) \tan \phi'$$

$$\text{Factor of Safety: } FS = \frac{\tau_f}{\tau_d} = \frac{c' + (\gamma z \cos^2 \alpha - u_w) \tan \phi'}{\gamma z \sin \alpha \cos \alpha}$$

### 🔍 Variable Definitions:
* $\tau_f$: Available soil shear strength ($\text{kPa}$).
* $\tau_d$: Gravitational driving shear stress along the slope ($\text{kPa}$).
* $c'$: Effective soil cohesion ($\text{kPa}$).
* $\sigma_n = \gamma z \cos^2 \alpha$: Total normal overburden stress ($\text{kPa}$).
* $u_w = \gamma_w h_w \cos^2 \alpha$: **Transient pore-water pressure ($\text{kPa}$)** induced by rainfall infiltration.
* $\phi'$: Effective internal friction angle of the soil/rock interface ($^\circ$).
* $\alpha$: Slope gradient ($^\circ$).
* $\gamma, \gamma_w$: Unit weights of soil and water ($\text{kN/m}^3$).
* $z, h_w$: Soil depth and perched groundwater table height ($\text{m}$).

### 📚 Academic Source & Citation:
* **Source:** Classical Soil Mechanics & USGS Transient Hydrological Response Model.
* **Reference:** Iverson, R. M. (2000). *Landslide triggering by rain infiltration*. **Water Resources Research (AGU)**, 36(7), 1897–1910.  
  🔗 [https://doi.org/10.1029/2000WR900090](https://doi.org/10.1029/2000WR900090)

---

# 3. TreeSHAP Game-Theoretic Marginal Factor Attribution

### 📝 Mathematical Formulation:
$$\phi_i(x) = \sum_{S \subseteq F \setminus \{i\}} \frac{|S|!(|F| - |S| - 1)!}{|F|!} \Big[f_x(S \cup \{i\}) - f_x(S)\Big]$$

$$\text{Additive Property: } f(x) = \phi_0 + \sum_{i=1}^{M} \phi_i(x)$$

### 🔍 Variable Definitions:
* $\phi_i(x)$: Shapley attribution value for physical factor $i$ (e.g. 3-day rain, slope, soil moisture).
* $F$: Complete set of all input features ($|F| = 15$).
* $S$: Any feature subset excluding feature $i$.
* $f_x(S) = \mathbb{E}[f(x) \mid x_S]$: Expected model output conditioned on subset $S$.
* $\phi_0 = \mathbb{E}[f(x)]$: Baseline average probability across the state ($\approx 0.12$).

### 📚 Academic Source & Citation:
* **Source:** Nature Machine Intelligence / NeurIPS Cooperative Game Theory.
* **Reference:** Lundberg, S. M., Erion, G., Chen, H., DeGrave, A., et al. (2020). *From local explanations to global understanding with explainable AI for trees*. **Nature Machine Intelligence**, 2(1), 56–67.  
  🔗 [https://doi.org/10.1038/s42256-019-0138-9](https://doi.org/10.1038/s42256-019-0138-9)

---

# 4. Topographic Wetness Index (TWI)

### 📝 Mathematical Formulation:
$$\text{TWI} = \ln\left(\frac{A_s}{\tan \beta}\right)$$

### 🔍 Variable Definitions:
* $A_s$: Specific upstream catchment area per unit contour length ($\text{m}^2/\text{m}$).
* $\beta$: Local terrain slope gradient (radians).
* **Physical Significance:** Quantifies topographic control on hydrological saturation zones and subsurface water pooling.

### 📚 Academic Source & Citation:
* **Reference:** Beven, K. J., & Kirkby, M. J. (1979). *A physically based, variable contributing area model of basin hydrology*. **Hydrological Sciences Bulletin**, 24(1), 43–69.  
  🔗 [https://doi.org/10.1080/02626667909491834](https://doi.org/10.1080/02626667909491834)

---

# 5. Stream Transport Index (STI / Sediment Transport)

### 📝 Mathematical Formulation:
$$\text{STI} = \left(\frac{A_s}{22.13}\right)^{0.6} \times \left(\frac{\sin \beta}{0.0896}\right)^{1.3}$$

### 🔍 Variable Definitions:
* $A_s$: Upstream contributing catchment area ($\text{m}$).
* $\beta$: Local slope angle (degrees).
* **Physical Significance:** Models overland flow shear erosivity and sediment carrying capacity along slope gullies.

### 📚 Academic Source & Citation:
* **Reference:** Moore, I. D., & Burch, G. J. (1986). *Sediment transport capacity of sheet and rill flow: Application of unit stream power theory*. **Water Resources Research**, 22(8), 1350–1360.  
  🔗 [https://doi.org/10.1029/WR022i008p01350](https://doi.org/10.1029/WR022i008p01350)

---

# 6. Cost-Sensitive XGBoost Objective & Asymmetric Loss

### 📝 Mathematical Formulation:
$$\mathcal{L}_{\text{CS}}(\theta) = -\sum_{i=1}^{N} \Big[ w_{\text{pos}} \cdot y_i \ln(p_i) + (1 - y_i) \ln(1 - p_i) \Big] + \sum_{k} \left( \gamma T_k + \frac{1}{2}\lambda \sum_{j=1}^{T_k} w_{kj}^2 + \alpha \sum_{j=1}^{T_k} |w_{kj}| \right)$$

### 🔍 Variable Definitions:
* $w_{\text{pos}} = \text{scale\_pos\_weight} = 14.2$: Penalizes False Negatives (missed slides) $14.2\times$ heavier than False Positives.
* $y_i \in \{0, 1\}$: Binary ground-truth landslide label.
* $p_i = \sigma(\hat{y}_i)$: Predicted probability.
* $\gamma = 1.8$: Tree split pruning complexity penalty.
* $\lambda = 3.5$: L2 Ridge regularization on leaf weights ($w_{kj}$).
* $\alpha = 1.2$: L1 Lasso regularization promoting sparsity.
* $T_k$: Number of terminal leaves in tree $k$.

### 📚 Academic Source & Citation:
* **Reference:** Chen, T., & Guestrin, C. (2016). *XGBoost: A Scalable Tree Boosting System*. **ACM SIGKDD International Conference**, 785–794.  
  🔗 [https://doi.org/10.1145/2939672.2939785](https://doi.org/10.1145/2939672.2939785)

---

# 7. Antecedent Precipitation Index (Hydrological Memory Decay)

### 📝 Mathematical Formulation:
$$\text{API}_t = \sum_{i=1}^{k} C^i \cdot P_{t-i} = P_t + C \cdot \text{API}_{t-1}$$

### 🔍 Variable Definitions:
* $\text{API}_t$: Antecedent Precipitation Index at day $t$ ($\text{mm}$).
* $P_{t-i}$: Daily precipitation $i$ days prior ($\text{mm}$).
* $C = 0.84$: Geological recession decay coefficient for Sikkim Himalayan metamorphic schists.
* $k = 7$: Antecedent hydrological window (7 days).

### 📚 Academic Source & Citation:
* **Reference:** Kohler, M. A., & Linsley, R. K. (1951). *Predicting the Runoff from Storm Rainfall*. **US Weather Bureau Research Paper**, No. 34.

---

# 8. Digital Elevation Model Terrain Derivatives (Sobel Operators)

### 📝 Mathematical Formulation:
$$p = \frac{\partial z}{\partial x} \approx \frac{(z_3 + 2z_6 + z_9) - (z_1 + 2z_4 + z_7)}{8 \cdot \Delta x}, \quad q = \frac{\partial z}{\partial y} \approx \frac{(z_1 + 2z_2 + z_3) - (z_7 + 2z_8 + z_9)}{8 \cdot \Delta y}$$

$$\text{Slope: } \text{Slope} = \arctan\left(\sqrt{p^2 + q^2}\right)$$

$$\text{Aspect: } \text{Aspect} = 270^\circ + \arctan2(q, -p)$$

### 📚 Academic Source & Citation:
* **Reference:** Horn, B. K. (1981). *Hill shading and the reflectance map*. **Proceedings of the IEEE**, 69(1), 14–47.  
  🔗 [https://doi.org/10.1109/PROC.1981.11918](https://doi.org/10.1109/PROC.1981.11918)
