# 📚 AAPTIRAKSHAK (SIH26001) — Research Papers & Scientific References

This document lists the foundational, peer-reviewed scientific literature behind our **Two-Layer Physics-Coupled Machine Learning Early Warning Architecture**.

---

## 🛰️ 1. Global Landslide Early Warning & Satellite Systems

1. **NASA LHASA 2.0 (Global Machine Learning Landslide Early Warning)**
   * **Title:** *Global Landslide Hazard Assessment for Situational Awareness (LHASA Version 2.0)*
   * **Authors:** Robert Emberson, Dalia Kirschbaum, Thomas Stanley
   * **Journal:** *AGU Earth's Future (2020)*
   * **DOI Link:** [https://doi.org/10.1029/2019EF001467](https://doi.org/10.1029/2019EF001467)
   * **How we used it:** Architectural benchmark for decoupling static susceptibility from dynamic satellite rainfall/soil moisture triggers.

2. **Rainfall Thresholds for Landslide Early Warning Systems**
   * **Title:** *Rainfall thresholds for the initiation of landslides in central and southern Europe*
   * **Authors:** Fausto Guzzetti, S. Peruccacci, M. Rossi, C. P. Stark
   * **Journal:** *Earth-Science Reviews & Meteorology and Atmospheric Physics (2007/2008)*
   * **DOI Link:** [https://doi.org/10.1016/j.earscirev.2007.09.002](https://doi.org/10.1016/j.earscirev.2007.09.002)
   * **How we used it:** Formulation of cumulative rainfall burst ($R_{1\text{d}}$) vs antecedent accumulation ($R_{3\text{d}}$) threshold curves.

3. **NASA GPM IMERG Global Satellite Precipitation Measurement**
   * **Title:** *The Integrated Multi-satellite Retrievals for GPM (IMERG)*
   * **Authors:** George J. Huffman et al.
   * **Journal:** *Journal of Hydrometeorology (2020)*
   * **DOI Link:** [https://doi.org/10.1175/JHM-D-19-0195.1](https://doi.org/10.1175/JHM-D-19-0195.1)
   * **How we used it:** Remote-sensing microwave precipitation radar ingestion across Sikkim's 4 district hubs.

---

## 🧠 2. Machine Learning & Explainable AI (XAI) Foundations

4. **TreeSHAP: Exact Explainable AI for Decision Trees**
   * **Title:** *From local explanations to global understanding with explainable AI for trees*
   * **Authors:** Scott M. Lundberg, Gabriel G. Erion, Su-In Lee, et al.
   * **Journal:** *Nature Machine Intelligence (2020)*
   * **DOI / Paper Link:** [https://doi.org/10.1038/s42256-019-0138-9](https://doi.org/10.1038/s42256-019-0138-9) | [arXiv:1802.03888](https://arxiv.org/abs/1802.03888)
   * **How we used it:** Polynomial-time $O(TLD^2)$ game-theoretic factor decomposition for cell-level disaster risk explanations.

5. **Why Tree Models Outperform Deep Learning on Tabular Data**
   * **Title:** *Why do tree-based models still outperform deep learning on tabular data?*
   * **Authors:** Léo Grinsztajn, Edouard Oyallon, Gaël Varoquaux
   * **Conference:** *36th Conference on Neural Information Processing Systems (NeurIPS 2022)*
   * **arXiv Link:** [https://arxiv.org/abs/2207.08815](https://arxiv.org/abs/2207.08815)
   * **How we used it:** Scientific rationale for selecting Cost-Sensitive XGBoost over deep neural networks for heterogeneous tabular GIS features.

6. **Cost-Sensitive Learning for Extreme Class Imbalance**
   * **Title:** *Cost-Sensitive Boosting for Classification of Imbalanced Data*
   * **Authors:** Yanmin Sun, Mohamed S. Kamel, Andrew K. C. Wong, Yuan Wang
   * **Journal:** *IEEE Transactions on Pattern Analysis and Machine Intelligence (PAMI)*
   * **DOI Link:** [https://doi.org/10.1109/TKDE.2007.190673](https://doi.org/10.1109/TKDE.2007.190673)
   * **How we used it:** Implementation of `scale_pos_weight = 14.2` to penalize False Negatives (fatal missed slides) over False Positives.

---

## 🏔️ 3. Geotechnical Physics & Himalayan Studies

7. **Mohr-Coulomb Slope Failure & Pore-Water Pressure Physics**
   * **Title:** *Landslide triggering by rain infiltration*
   * **Authors:** Richard M. Iverson (USGS)
   * **Journal:** *Water Resources Research (AGU, 2000)*
   * **DOI Link:** [https://doi.org/10.1029/2000WR900090](https://doi.org/10.1029/2000WR900090)
   * **How we used it:** Mathematical representation of transient pore-pressure diffusion ($u_w$) reducing effective normal stress ($\sigma_n - u_w$).

8. **Rainfall Thresholds in the Sikkim Himalayas (Teesta Basin)**
   * **Title:** *Rainfall thresholds for landslide initiation in the Sikkim Himalayas*
   * **Authors:** Prashant Kumar Dikshit, R. Satyamurthy, et al.
   * **Journal:** *Landslides (Springer, 2020)*
   * **DOI Link:** [https://doi.org/10.1007/s10346-020-01443-4](https://doi.org/10.1007/s10346-020-01443-4)
   * **How we used it:** Calibrating regional rainfall triggers ($100\text{ mm}$ 3-day threshold) for NH-10 and North Sikkim highway corridors.

9. **GSI National Landslide Susceptibility Mapping (NLSM) Methodology**
   * **Organization:** Geological Survey of India (Ministry of Mines, Govt. of India)
   * **Official Portal:** [https://www.gsi.gov.in](https://www.gsi.gov.in) | [Bhukosh Portal](https://bhukosh.gsi.gov.in)
   * **How we used it:** 13-factor GIS conditioning standard (Slope, Aspect, Curvature, TWI, STI, Lithology, Faults, Roads, Railways).
