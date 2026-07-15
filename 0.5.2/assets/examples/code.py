import matplotlib.pyplot as plt
import numpy as np
import numpy.typing as npt


# Constants
E0 = 50.0  # Reference modulus (MPa)
T0 = 10.0  # Reference temperature (°C)
alpha = 0.02  # Thermal softening coefficient
beta = 0.15  # Strain-rate sensitivity
eps_dot0 = 1.0  # Reference strain rate


ArrayLike = npt.NDArray[np.float64] | float


def modulus(temperature: ArrayLike, strain_rate: float) -> ArrayLike:
    """Return elastic modulus as a function of temperature and strain rate."""
    return E0 * (1 - alpha * (temperature - T0)) * (1 + beta * np.log(strain_rate / eps_dot0))


# Compute modulus for a range of temperatures
temperatures = np.linspace(5, 25, 100)
rates = [0.1, 1, 10]

plt.figure(figsize=(6, 4))
for r in rates:
    plt.plot(temperatures, modulus(temperatures, r), label=f"ε̇ = {r} s⁻¹")
plt.xlabel("Temperature (°C)")
plt.ylabel("Elastic Modulus E (MPa)")
plt.title("Temperature Dependence of Cheese Stiffness")
plt.legend()
plt.grid(True)
plt.tight_layout()
plt.show()
