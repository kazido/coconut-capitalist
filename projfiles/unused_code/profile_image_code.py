# avatar = user.instance.avatar
        #
        # async def set_avatar(selected_gender, selected_number, avatar_interaction):
        #     user.instance.avatar = f'{selected_gender}.{selected_number}'
        #     await avatar_interaction.response.edit_message(view=None)
        #     await bal_command(f'{selected_gender}.{selected_number}')
        #
        # async def bal_command(user_avatar):
        #     gender, number = user_avatar.split('.')[0], user_avatar.split('.')[1]
        #
        #     image1 = Image.open(project_files / 'templates' / 'blank_template.png')
        #     font = ImageFont.truetype(str(project_files / 'fonts' / 'StaatlichesRegular.ttf'), 25)
        #     smallerfont = ImageFont.truetype(str(project_files / 'fonts' / 'StaatlichesRegular.ttf'), 18)
        #
        #     rank = user.rank
        #     name = f'{interaction.user.name} #{interaction.user.discriminator}'
        #     bits = user.instance.money
        #     tokens = user.instance.tokens
        #     bank = user.instance.bank
        #     digging_level = 0
        #     fishing_level = 0
        #     mining_level = 0
        #     combat_level = 0
        #
        #     image_editable = ImageDraw.Draw(image1)
        #     # # Draw pet
        #     # pet = await ctx.bot.dbpets.find_one({"owner_id": ctx.author.id, "active": True})
        #     # if pet:
        #     #     pet_sprite = Image.open(project_files / 'sprites' / f'{pet["species"]}_sprite.png')
        #     #     pet_name = pet["name"]
        #     #     image1.paste(pet_sprite, (636, 70), pet_sprite)
        #     #     if len(pet_name) > 8:
        #     #         image_editable.text((677, 187), pet_name, (238, 131, 255), font=smallerfont, anchor='mm')
        #     #     else:
        #     #         image_editable.text((677, 187), pet_name, (238, 131, 255), font=font, anchor='mm')
        #
        #     # Draw avatar
        #     avatar_to_draw = Image.open(project_files / 'sprites' / f'{gender}_avatar_{number}.png')
        #     image1.paste(avatar_to_draw, (85, 45), avatar_to_draw)
        #
        #     # Draw Name
        #     image_editable.text((203, 317), name, (255, 255, 255), font=font, anchor='mm')
        #
        #     # Draw rank and tokens
        #     image_editable.text((678, 293), rank.name, (44, 255, 174), font=font, anchor='mm')
        #     image_editable.text((678, 370), '{:,}'.format(tokens), (44, 255, 174), font=font, anchor='mm')
        #
        #     # Draw bits
        #     image_editable.text((489, 120), '{:,}'.format(bits), (255, 241, 138), font=font, anchor='mm')
        #     image_editable.text((489, 186), '{:,}'.format(bank), (255, 241, 138), font=font, anchor='mm')
        #
        #     # Draw levels
        #     image_editable.text((116, 410), f"Rank {'{:,}'.format(digging_level)}", (197, 255, 176), font=font,
        #                         anchor='mm')
        #     image_editable.text((285, 410), f"Rank {'{:,}'.format(fishing_level)}", (168, 208, 255), font=font,
        #                         anchor='mm')
        #     image_editable.text((116, 509), f"Rank {'{:,}'.format(mining_level)}", (255, 211, 150), font=font,
        #                         anchor='mm')
        #     image_editable.text((285, 509), f"Rank {'{:,}'.format(combat_level)}", (255, 170, 170), font=font,
        #                         anchor='mm')
        #
        #     with BytesIO() as image_binary:
        #         image1.save(image_binary, 'PNG')
        #         image_binary.seek(0)
        #         await interaction.response.defer(thinking=True)
        #         await interaction.followup.send_message(file=discord.File(fp=image_binary, filename='image.png'))

        # if avatar == "None":
        #     await interaction.response.send_message("Hey... It looks like you don't have an avatar selected yet.\n"
        #                                             "Please pick one now!")
        #     await asyncio.sleep(0.3)
        #
        #     class CharacterSelectButtons(discord.ui.View):
        #         def __init__(self, *, timeout=180):
        #             super().__init__(timeout=timeout)
        #
        #         async def on_timeout(self) -> None:
        #             await message.delete()
        #
        #         @discord.ui.button(label="1", style=discord.ButtonStyle.blurple)
        #         async def male_1(self, button1interaction: discord.Interaction, button: discord.ui.Button):
        #             if button1interaction.user != interaction.user:
        #                 return
        #             await set_avatar('male', '1', button1interaction)
        #
        #         @discord.ui.button(label="2", style=discord.ButtonStyle.blurple)
        #         async def male_2(self, button2interaction: discord.Interaction, button: discord.ui.Button):
        #             if button2interaction.user != interaction.user:
        #                 return
        #             await set_avatar('male', '2', button2interaction)
        #
        #         @discord.ui.button(label="3", style=discord.ButtonStyle.blurple)
        #         async def male_3(self, button3interaction: discord.Interaction, button: discord.ui.Button):
        #             if button3interaction.user != interaction.user:
        #                 return
        #             await set_avatar('male', '3', button3interaction)
        #
        #         @discord.ui.button(label="4", style=discord.ButtonStyle.blurple, row=1)
        #         async def female_1(self, button4interaction: discord.Interaction, button: discord.ui.Button):
        #             if button4interaction.user != interaction.user:
        #                 return
        #             await set_avatar('female', '1', button4interaction)
        #
        #         @discord.ui.button(label="5", style=discord.ButtonStyle.blurple, row=1)
        #         async def female_2(self, button5interaction: discord.Interaction, button: discord.ui.Button):
        #             if button5interaction.user != interaction.user:
        #                 return
        #             await set_avatar('female', '2', button5interaction)
        #
        #         @discord.ui.button(label="6", style=discord.ButtonStyle.blurple, row=1)
        #         async def female_3(self, button6interaction: discord.Interaction, button: discord.ui.Button):
        #             if button6interaction.user != interaction.user:
        #                 return
        #             await set_avatar('female', '3', button6interaction)
        #
        #     message = await interaction.response.send_message(
        #         file=discord.File(project_files / 'templates' / 'CharacterSelect.png'),
        #         view=CharacterSelectButtons())
        #     return
        # else:
        #     await bal_command(avatar)