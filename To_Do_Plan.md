#Retrain the Yolo model (for defect detection) seperate from detection model
- Because the current trained with the dataset of full board and in the demo we have use SHAHI to crop and divide the image into smaller parts > Yolo detect > Golden template > Stich back to full board > Fetch coordinate

##Use model quantinization or it over kill when we only deploy it localy
##Analyze the latency and number of phone and image the system can handle at once
##The limitations of local pc act as a server
##The limitations of DB and how the DB handled
##What define the mobile app , what the difference between the reality product and the demo
##What to compare and what the number and statistic to evaluate for the demo
##What is Active Learning or a Data Flywheel
##The Feedback API Route architecture and logic
##If the math in this single API route is off by even a few decimal places, you will successfully train your YOLO model... to look at the completely wrong pixels. It will confidently learn garbage, and your Flywheel will become a poison dispenser. (How to fix this, Name solutions)
##What if when we selected image for the correct ai mistakes, and we pick the wrong photos. What will happen, analyze the cause and find the fix for this one (do we save the image cache or something else)
##The correct ai mistakes have a problem when we select the full board and we draw the bounding box, 1. We can draw it overlap with small component that near it, 2. It too difficult to draw for the small component

##Clean the connector or remove it, analyze if we should keep the resistor or not because it the smallest component in the board and we can only use SHAHI to detect it. If i want to keep what the change in the logic and operate pipeline to do solve that

<!-- The Execution: It programmatically triggers the YOLO CLI: yolo task=detect mode=train data=dataset.yaml model=SAVE_model/best.pt epochs=50. (Notice it uses the current best model as the starting point, making it smarter incrementally).
+ We need to save 2 model the previous and the after train version 
+ Do we need to compare the 2 model, if yes what will be the test set. can you describe the test set example the test set have to be sharp/blur, it have to be a new image of board/component,... -->
<!-- This is how senior developers solve naive AI. We do not throw more open-source data at it; we build pipelines that trick the user into generating hyper-specific, perfect training data for us.
What will be the downside or not good or good or an improvement on difference facts and real life laws, example how can we protect the privacy for each client, the solution have a authentical function so each user can protect their privacy weight, the obstacle the DB to store for each user and the enscription method, The surviability of the product what if it cause the amnisia in the model, we need to have a plan for these kind of problems.
Your current job is to list all of the problems like the example and more , list at least 10 problem and rate it from good to have to importance to needed to have
Give me the solutions for the needed to have problems and compare it with the modern ways to solve it and the commercial way to solve it.-->

<!-- The problem is we can only draw <Svg> layer as a square or rectange if it affect the retrain -->
