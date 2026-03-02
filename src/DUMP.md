




1. Option C
2. Look into our current pagination scheme. Use something coherent with it 
3. Batch queries for now!


, and it should support multiple tables (e.g Product Favorites, Posts favorites etc.). This  
  is done as a test case for the new list functionnality of supporting multipl tables!     



Likes always show 0 on comment, even after successfull like                                                                         



Let's improve our claude.md file 
                                                                                                                                      
  First up, there are some very long lines at the beginning. We should add some returns in order for them to be properly displayed    
  in any IDE and not have to horizontal scroll.                                                                                       
                                                                                                                                      
  We should also add the section before architecture overview, that is the regular workflows we implement for making changes.         
                                                                                                                                      
  In this section we'd like to have a part that talks about first properly reviewing the changes we are to make, makesure they align  
  with the intent bhind the code to keep a consistent project. We also need to really stress out in a few sentences the importance    
  to keep the project consistent, to always use the architecture that is already in place instead of doing hackarounds to solve       
  things.                                                                                                                             
                                                                                                                                      
  Also in this section, we'd like to have a small section on bug fixes. You can lay down the regular approaches to do bug fixes.      
  But we'd like to add our own whereas To express that usually bugs that are 
  created by the devs are the symptoms of either them not understanding the structure, the intent, of the
  current code and system and not making their changes consistent with the current architecture. Or that the architecture is not      
  clear enough or doesn't provide a decent way of doing what they are trying to do. In both cases, it should be noted that in order   
  to fix the bug, we need to first review what caused the bug. Is this just a simple programming mistake, or is it the symptom of     
  something larger, like we just mentioned? If it's the second part, then we need to re-evaluate the bigger picture and see if we     
  either need to improve the documentation so it doesn't happen anymore, or if we need to actually do some deeper changes within the  
  architecture in order to simplify something to solve thw problem elegantly!
  

Great,we are making great progress!
An agent is building Wave 1 in the background and while they do it we are 
ready for wave 2!                                                                                                    
                                                                                                                                        
Like before we should always go over the proposed changed together, see the 
different approaches we could take, the tradeoffs, different gotchas, 
clarify ambivalent information etc.. Once we find the optimal way to execute 
on the task we can commit to it ans write the changes.
When compacting the conversation, keep those instructions as is! 