# Scooter Charging Station Project

This is the repository for the Capstone II Scooter Charging Station project and contains all related code.

## About Project

On the University of Missouri Science and Technology campus, many students choose to use electronic scooters to travel across campus. The university, however, has a strict policy stating that electronic scooters may not be brought into campus buildings. With no way to safely charge their scooters, students whos scooters run out of battery while on campus have no way of recharging them without breaking this rule. The Scooter Charging Station project aims to provide a safe and convenient way for students to charge their electronic scooters while on campus. 

Lockers will be placed around campus in various high-traffic areas. Inside the lockers, there will be a standard power outlet that students may plug their own personal charging devices into to charge them. The lockers, while closed, will be locked and unable to be opened by anyone except the student who's items are inside and StuCo. Students will be able to reserve a locker via a website, and unlock the locker door while their reservation remains active.

Originally, this project was undertaken by a senior design group in the Electrical Engineering program. This project was to be worked on over the course of two semesters. At the beginning of the second semester, a group member who was dual majoring in Electrical Engineering and Computer Science proposed the webserver programming portion as a Computer Science Capstone II project. This repository contains all code that was worked on by the Capstone II group members.

## Repository Structure

There are two main directories in this repository.
1. `client`
2. `webserver`

`client` contains code that runs on the Raspberry Pi that is contained in each scooter charging station.
`webserver` contains code that runs the webserver that facilitates the connection between itself and the charging stations, and also serves the various webpages that allows users to reserve and unlock lockers.

For more information, please refer to the READMEs that are contained in either of these repositories.