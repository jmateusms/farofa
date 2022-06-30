# farofa - **f**ailure **a**nd **r**epair simulation **o**ptimization **f**r**a**mework

This project aims to create a framework for failure-repair simulation with modularity in mind. farofa is in very (very) early development stages, and **is not yet ready to use**. I have a vague roadmap for this project, which is detailed [below](#roadmap), but you can expect changes and details in the future.

## what does it do?

Right now, not much. But here's a brief overview of what I intend to include over the coming months.

In summary, this module should allow users to perform failure-repair simulations for multiple types of scenarios, such as considering different types of failure and repair time distributions, multiple devices in queueing systems, different priority classes, competing risks models. It should also allow users to create their own scenarios, in addition to using existing scenarios.

Beyond the simulation itself, farofa should be able to output the most commonly used metrics in literature, for these types of problems. Of course, users should be able to include custom metrics as they desire. Moreover, farofa should be able to perform optimization in respect to some of the metrics it outputs.

## implementation

Concerning performance, Numba is being used to accelerate simulations. But since I intend to allow custom failure/repair behavior, as well as custom objective functions, I am looking into how to allow the user to choose whether or not to use Numba when importing or calling functions.

## roadmap

This is a general list of what I expect to include in this project. The order is more or less what I would expect to achieve. However, it is entirely possible that some features will be implemented sooner or later than expected.

- [ ] "v0"
  - [ ] Simple failure-repair simulation framework with a limited set of time distributions.
  - [ ] Include most common distributions for failure and repair times.
  - [ ] Allow usage of custom time distributions.
  - [ ] Formatted output with most used metrics.
- [ ] "v1"
  - [ ] Include a queueing system, where multiple devices of the same behavior are simulated.
  - [ ] Implement most common queue models.
  - [ ] Allow usage of custom queue models.
- [ ] "v2"
  - [ ] Allow devices of different types in the same simulation.
  - [ ] Include priority queue options.
  - [ ] Increase the number of metrics.
- [ ] "v3"
  - [ ] Add an optimization framework.
  - [ ] Allow setting custom objective functions, such as cost/profit/return/wealth functions.
- [ ] "v4"
  - [ ] Create a GUI.
- [ ] "v5"
  - [ ] Perform parameter estimation from failure data (there are existing tools that can do that).

## inspiration

These are are some of the works that inspired the ideas for farofa. In the future, I would like farofa to be able to replicate the results of these works, or at least provide functionality to perform the most relevant parts of them.

- Moura, M. C., Santana, J. M., Droguett, E. L., Lins, I. D., Guedes, B. N. (2017). Analysis of extended warranties for medical equipment: A Stackelberg game model using priority queues. Reliability Engineering \& System Safety, 168, 338–354. ([DOI](https://doi.org/10.1016/j.ress.2017.05.040)).
- Santana, J. M., Santiago, R. L. V., Moura, M. D. C., Lins, I. D. (2018). Extended warranty of medical equipment subject to imperfect repairs : an approach based on generalized renewal process and Stackelberg game. Eksploatacja I Niezawodnosc, 20(4), 567–578. ([DOI](https://doi.org/10.17531/ein.2018.4.8)).
- Yañez, M., Joglar, F., Modarres, M. (2002). Generalized renewal process for analysis of repairable systems with limited failure experience. Reliability Engineering and System Safety, 77(2), 167–180. ([DOI](https://doi.org/10.1016/S0951-8320(02)00044-3)).
- Wang, Z. M., Yang, J. G. (2012). Numerical method for Weibull generalized renewal process and its applications in reliability analysis of NC machine tools. Computers and Industrial Engineering. ([DOI](https://doi.org/10.1016/j.cie.2012.06.019))
- Moura, M. C., Droguett, E. L., Alves Firmino, P. R., Ferreira, R. J. (2014). A competing risk model for dependent and imperfect condition-based preventive and corrective maintenances. Proceedings of the Institution of Mechanical Engineers Part O-Journal of Risk and Reliability, 228(6), 590–605. ([DOI](https://doi.org/10.1177/1748006X14540878)).
