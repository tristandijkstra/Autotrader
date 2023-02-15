# Autotrader
_Disclaimer: This is a stripped down version of the first autotrader I made, published on a fresh repository because of the possibility of leaks. The original project was created sporadically between early 2021 and mid 2022 over ~170 commits. The code in the form presented here is not functional nor profitable, it merely serves as portfolio piece._

## Why crypto?
Without sharing opinions on the pragmatisms of crypto: crypto was used because it is volatile and accessible financially and in terms of APIs.

## Reflection on the project
### Things learned
Much of my current programming habits and skills originate from this project:
 - Code quality - the project was built in spare time between school, as such it was very important to have readable, well documented code to come back to. This project initiated my use of docstrings, typehints and formatting, which are used extensively in my projects after this one.
 - Extensive use of pandas, data exploration, data clean up, data engineering.
 - Use of logging for large projects.
 - Docker.
 - Basic understanding of threading in python.
 - Considerations in timing.
 - __Testing Testing Testing.__ Good testing, exception catching and logs are crucial when testing a program that may take days to properly diagnose.

### Things I would do differently next time
 - An event base architecture instead of an iterative one. It would have been better to use classes and events that trigger methods. A collection of classes would initiate and call eachother. For example: A websocket price update may call a strategy class which calls a method in a trader class to buy. This removes a lot of hastle with timing, and improves robustness and traceability. If a threaded websocket architecture is used, no loop is even needed.
 - Look at examples: in retrospect  there were way more bots on github I could have used as inspiration.
 - More tests: it would have helped to ensure compatibility and tracibility when remaking old code.
 - Better care with API keys and other information that should have been held hidden. Otherwise this would have been the original repo :).
 - Use SQL, to store the data.

While, there was certainly a thrill in building a bot from scratch, the strategy is ultimately the most fun part. I recommend considering using an existing library/bot on github if you are considering trying this out.